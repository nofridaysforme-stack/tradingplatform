"""Chronological replay (spec 12). Uses the live strategy and lifecycle modules unchanged.

for each completed M15 bar, oldest first:
    skip it if forex was closed when it completed (as the live job does)
    at a new trading day, take that day's levels (built from data through the prior close)
    track every open simulated signal against the bar
    evaluate the strategies on the same bar window the live job uses
    record new signals (deduplicated like the live unique index)

Results are measured on mid prices; the cost model then takes off spread and slippage.
"""

import logging
from bisect import bisect_left
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd

from scanner.backtest.costs import CostModel
from scanner.data.base import Candle
from scanner.indicators.base import Bars
from scanner.instruments import Instrument
from scanner.levels.compute import build_levels
from scanner.rules.registry import RuleSet
from scanner.signals.lifecycle import CLOSED, BarView, TrackedSignal, track
from scanner.signals.store import bars_since
from scanner.strategies import fib_pivot, three_eight
from scanner.strategies.common import (
    BAR,
    Context,
    EconEvent,
    InstrumentRef,
    PriorSignal,
    SignalDraft,
    in_window,
    trading_windows,
)
from scanner.time import (
    is_forex_open,
    previous_forex_trading_day,
    trading_day_of,
    trading_day_start,
)

log = logging.getLogger(__name__)

WINDOW_BARS = 600  # same window the live job hands the strategies (jobs/runtime.py)
PRIOR_DAYS = 3
STRATEGIES = {"three_eight": three_eight, "fib_pivot": fib_pivot}
LevelsFor = Callable[[date], dict[str, dict[str, Any]]]


@dataclass
class SimTrade:
    signal: SignalDraft
    state: str = "open"
    closed_at: datetime | None = None
    exit_price: float | None = None
    gross_pips: float | None = None
    net_pips: float | None = None
    events: list[str] = field(default_factory=list)

    @property
    def closed(self) -> bool:
        return self.state in CLOSED


@dataclass
class EngineResult:
    instrument: str
    trades: list[SimTrade] = field(default_factory=list)
    rejections: Counter[str] = field(default_factory=Counter)
    bars: int = 0
    evaluated: int = 0
    outside_window: int = 0


def _window_closed(
    rules: RuleSet, iid: UUID, strategies: Sequence[str], close_time: datetime
) -> bool:
    """True when every strategy's trading window gate would reject this bar. Skipping the
    evaluation then changes no signal, only the rejection counts (reported separately)."""
    shared = rules.params("three_eight.trading_window", iid)
    for name in strategies:
        key = "three_eight.trading_window" if name == "three_eight" else "fib_pivot.window"
        if not rules.enabled(key):
            return False
        which = shared["window"] if name == "three_eight" else rules.params(key, iid)["window"]
        if any(in_window(close_time, a, b) for a, b in trading_windows(shared, which)):
            return False
    return True


def run_pair(
    inst: InstrumentRef,
    m15: pd.DataFrame,
    levels_for: LevelsFor,
    rules: RuleSet,
    costs: CostModel,
    strategies: Sequence[str] = ("three_eight", "fib_pivot"),
    econ_events: Sequence[EconEvent] = (),
    holidays: frozenset[date] = frozenset(),
    evaluate_from: datetime | None = None,
    skip_outside_window: bool = True,
    on_progress: Callable[[int, int], None] | None = None,
) -> EngineResult:
    ts: list[datetime] = [t.to_pydatetime() for t in pd.to_datetime(m15["ts"], utc=True)]
    o = m15["o"].to_numpy(np.float64)
    h = m15["h"].to_numpy(np.float64)
    lo = m15["l"].to_numpy(np.float64)
    c = m15["c"].to_numpy(np.float64)
    n = len(ts)
    result = EngineResult(inst.symbol, bars=n)
    expiry = (
        rules.params("three_eight.expiry", inst.id) if rules.enabled("three_eight.expiry") else None
    )
    window = rules.params("three_eight.trading_window", inst.id)
    events = sorted(econ_events, key=lambda e: e.at)
    event_times = [e.at for e in events]

    open_sims: list[tuple[TrackedSignal, SimTrade]] = []
    prior: list[PriorSignal] = []
    seen: set[str] = set()
    current_day: date | None = None
    levels: dict[str, dict[str, Any]] = {}

    for i in range(n):
        bar_ts = ts[i]
        close_time = bar_ts + BAR
        if not is_forex_open(close_time - timedelta(minutes=1), holidays):
            continue
        day = trading_day_of(bar_ts)
        if day != current_day:
            current_day = day
            levels = levels_for(day)
            cutoff = day - timedelta(days=PRIOR_DAYS)
            prior = [p for p in prior if p.trading_day >= cutoff]

        # 1. Outcomes for open signals, before new candidates (spec 10).
        bar = BarView(bar_ts, float(o[i]), float(h[i]), float(lo[i]), float(c[i]))
        still_open = []
        for sig, trade in open_sims:
            out = track(
                sig, bar, bars_since=bars_since(sig.bar_ts, bar_ts), three_eight_expiry=expiry,
                trading_window=window, window=window["window"],
            )  # fmt: skip
            trade.events += [e.kind for e in out.events]
            if out.state is not None:
                sig.state = out.state
            if any(e.kind == "reset_reached" for e in out.events):
                sig.reset_reached = True
            if out.closed:
                trade.state = str(out.state)
                trade.closed_at = out.closed_at
                trade.exit_price = out.exit_price
                trade.gross_pips = out.result_pips
                trade.net_pips = costs.net(out.result_pips or 0.0, trade.state)
                _close_prior(prior, trade)
            else:
                still_open.append((sig, trade))
        open_sims = still_open

        # 2. New candidates on this bar.
        if evaluate_from is not None and bar_ts < evaluate_from:
            continue
        if skip_outside_window and _window_closed(rules, inst.id, strategies, close_time):
            result.outside_window += 1
            continue
        start = max(0, i - WINDOW_BARS + 1)
        lo_ev = bisect_left(event_times, close_time - timedelta(hours=6))
        hi_ev = bisect_left(event_times, close_time + timedelta(seconds=1))
        ctx = Context(
            instrument=inst,
            bars=Bars(
                ts[start : i + 1],
                o[start : i + 1],
                h[start : i + 1],
                lo[start : i + 1],
                c[start : i + 1],
            ),
            trading_day=day,
            levels=levels,
            rules=rules,
            econ_events=events[lo_ev:hi_ev],
            prior_signals=list(prior),
        )
        result.evaluated += 1
        for name in strategies:
            ev = STRATEGIES[name].evaluate(ctx)
            for r in ev.rejections:
                result.rejections.update(r.failed)
            for draft in ev.signals:
                if draft.dedupe_key in seen:
                    continue
                seen.add(draft.dedupe_key)
                trade = SimTrade(draft)
                result.trades.append(trade)
                open_sims.append((_tracked(draft, inst.pip_size), trade))
                prior.append(
                    PriorSignal(draft.strategy, draft.direction, draft.bar_ts, draft.trading_day)
                )
        if on_progress and i % 5000 == 0:
            on_progress(i, n)
    return result


def _tracked(draft: SignalDraft, pip_size: float) -> TrackedSignal:
    return TrackedSignal(
        id=draft.dedupe_key, strategy=draft.strategy, direction=draft.direction, state="open",
        bar_ts=draft.bar_ts, trading_day=draft.trading_day, entry=draft.entry, stop=draft.stop,
        target=draft.target, pip_size=pip_size,
        confirmation=draft.context.get("confirmation"), reset=draft.context.get("reset"),
    )  # fmt: skip


def _close_prior(prior: list[PriorSignal], trade: SimTrade) -> None:
    s = trade.signal
    for k, p in enumerate(prior):
        if p.strategy == s.strategy and p.bar_ts == s.bar_ts and p.direction == s.direction:
            prior[k] = PriorSignal(
                p.strategy, p.direction, p.bar_ts, p.trading_day, True, trade.gross_pips
            )
            return


# Levels from history


Row = tuple[datetime, float, float, float, float]


def rows_of(df: pd.DataFrame) -> list[Row]:
    """Plain (ts, o, h, l, c) tuples, oldest first."""
    stamps = [t.to_pydatetime() for t in pd.to_datetime(df["ts"], utc=True)]
    cols = [df[k].astype(float).tolist() for k in ("o", "h", "l", "c")]
    return list(zip(stamps, *cols, strict=True))


def _candle(code: str, gran: str, row: Row) -> Candle:
    ts, o, h, low, c = row
    return Candle(
        instrument=code, granularity=gran, ts=ts, o=Decimal(repr(o)), h=Decimal(repr(h)),
        l=Decimal(repr(low)), c=Decimal(repr(c)), volume=0, complete=True,
    )  # fmt: skip


def levels_from_history(
    inst: Instrument,
    daily: pd.DataFrame,
    weekly: pd.DataFrame,
    monthly: pd.DataFrame,
    rules: RuleSet,
    holidays: frozenset[date] = frozenset(),
) -> LevelsFor:
    """Levels for day D from candles that closed before D opened, exactly as the live day
    roll does (scanner.levels.compute): no look-ahead."""
    by_ts = {row[0]: row for row in rows_of(daily)}
    w_rows = rows_of(weekly)
    m_rows = rows_of(monthly)
    w_ts = [r[0] for r in w_rows]
    m_ts = [r[0] for r in m_rows]
    fib_params = {
        **rules.params("fib_pivot.unit", inst.id),
        **rules.params("fib_pivot.levels", inst.id),
    }
    cache: dict[date, dict[str, dict[str, Any]]] = {}

    def last_before(
        rows: list[Row], stamps: list[datetime], before: datetime, gran: str
    ) -> Candle | None:
        k = bisect_left(stamps, before) - 1
        return _candle(inst.provider_code, gran, rows[k]) if k >= 0 else None

    def levels_for(day: date) -> dict[str, dict[str, Any]]:
        if day in cache:
            return cache[day]
        prior_day = previous_forex_trading_day(day, holidays)
        d_row = by_ts.get(trading_day_start(prior_day))
        monday = day - timedelta(days=day.weekday())
        sets = build_levels(
            inst,
            daily=_candle(inst.provider_code, "D", d_row) if d_row is not None else None,
            weekly=last_before(w_rows, w_ts, trading_day_start(monday), "W"),
            monthly=last_before(m_rows, m_ts, trading_day_start(day.replace(day=1)), "M"),
            fib_params=fib_params,
        )
        cache[day] = sets
        return sets

    return levels_for


def utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC)
