"""Shared plumbing for jobs: building a strategy Context from the database and running both
forex strategies on one bar. The backtester builds the same Context from history."""

import logging
from datetime import date, datetime, timedelta
from typing import Any

from scanner import db
from scanner.indicators.base import Bars
from scanner.instruments import Instrument
from scanner.rules.registry import RuleSet
from scanner.signals import store
from scanner.strategies import fib_pivot, three_eight
from scanner.strategies.common import Context, EconEvent, Evaluation, InstrumentRef
from scanner.time import trading_day_of

log = logging.getLogger(__name__)

# M15 bars handed to the strategies: covers the trendline age limit (480) with room for swings.
WINDOW_BARS = 600
ECON_LOOKBACK = timedelta(hours=6)


def instrument_ref(inst: Instrument) -> InstrumentRef:
    return InstrumentRef(inst.id, inst.symbol, float(inst.pip_size), inst.display_decimals)


def build_context(conn: db.Conn, inst: Instrument, bar_ts: datetime, rules: RuleSet) -> Context:
    rows = db.recent_candles(conn, inst.id, "M15", bar_ts, WINDOW_BARS)
    day = trading_day_of(bar_ts)
    events = [
        EconEvent(at, cur, impact)
        for at, cur, impact in db.econ_events(
            conn, bar_ts - ECON_LOOKBACK, bar_ts + timedelta(minutes=15)
        )
    ]
    return Context(
        instrument=instrument_ref(inst),
        bars=Bars.from_rows(rows),
        trading_day=day,
        levels=db.get_levels(conn, inst.id, day),
        rules=rules,
        econ_events=events,
        prior_signals=store.prior_signals(conn, inst.id, day - timedelta(days=3)),
    )


def strategy_on(
    configs: dict[str, tuple[bool, list[Any] | None]], strategy: str, inst: Instrument
) -> bool:
    enabled, only = configs.get(strategy, (True, None))
    return enabled and (only is None or inst.id in only)


def evaluate_bar(
    conn: db.Conn,
    inst: Instrument,
    bar_ts: datetime,
    rules: RuleSet,
    configs: dict[str, tuple[bool, list[Any] | None]],
) -> dict[str, Any]:
    """Run both forex strategies on one completed bar and write any signals."""
    ctx = build_context(conn, inst, bar_ts, rules)
    written: list[str] = []
    rejected = 0
    confluence_bars = int(rules.params("fib_pivot.confluence", inst.id)["confluence_bars"])
    for name, module in (("three_eight", three_eight), ("fib_pivot", fib_pivot)):
        if not strategy_on(configs, name, inst):
            continue
        ev: Evaluation = module.evaluate(ctx)
        rejected += len(ev.rejections)
        for r in ev.rejections:
            log.debug("candidate rejected", extra={"strategy": name, "failed": r.failed})
        for draft in ev.signals:
            sid = store.write_signal(conn, draft)
            if sid is None:
                continue
            written.append(str(sid))
            if rules.enabled("fib_pivot.confluence"):
                store.mark_confluence(conn, sid, draft, confluence_bars)
            log.info("signal", extra={"signal_id": str(sid), "dedupe_key": draft.dedupe_key})
    return {"signals": written, "rejected": rejected}


def day_of(ts: datetime) -> date:
    return trading_day_of(ts)
