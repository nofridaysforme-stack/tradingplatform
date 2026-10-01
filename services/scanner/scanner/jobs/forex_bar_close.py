"""forex_bar_close (spec 03, spec 16): runs at minutes 0, 15, 30, 45 (second 5) while forex
is open. For each enabled pair: fetch the latest candles, store the completed ones, and for
each new completed bar track open signals, then evaluate both strategies."""

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, Protocol

from scanner import db
from scanner.data.base import Candle, completed
from scanner.instruments import Instrument
from scanner.jobs.runtime import evaluate_bar, strategy_on
from scanner.rules.registry import Registry
from scanner.signals import store
from scanner.signals.lifecycle import BarView, track
from scanner.time import is_forex_open

log = logging.getLogger(__name__)

FETCH_COUNT = 8  # enough to recover a few missed bars after a short outage


class CandleSource(Protocol):
    def candles(
        self,
        instrument: str,
        granularity: str,
        start: datetime | None = ...,
        end: datetime | None = ...,
        count: int | None = ...,
    ) -> list[Candle]: ...


def run(
    conn: db.Conn,
    source: CandleSource,
    registry: Registry,
    now: datetime,
    instruments: Sequence[Instrument] | None = None,
) -> dict[str, Any]:
    """Returns {"stale": [symbols with no new completed bar], "instruments": {...}}."""
    holidays = db.holidays(conn, "forex")
    # The bar that just completed closed a moment ago: Friday's 16:45 bar completes at 17:00,
    # after the market itself has closed.
    if not is_forex_open(now - timedelta(minutes=1), holidays):
        return {"skipped": "market closed", "stale": []}
    registry.refresh(conn)
    rules = registry.ruleset
    configs = db.strategy_configs(conn)
    detail: dict[str, Any] = {"instruments": {}, "stale": []}
    for inst in instruments if instruments is not None else db.list_instruments(conn):
        if not any(strategy_on(configs, s, inst) for s in ("three_eight", "fib_pivot")):
            continue
        before = db.latest_candle_ts(conn, inst.id, "M15")
        fresh = completed(source.candles(inst.provider_code, "M15", count=FETCH_COUNT))
        with conn.transaction():
            db.upsert_candles(conn, inst.id, fresh)
        new = sorted((c for c in fresh if before is None or c.ts > before), key=lambda c: c.ts)
        if not new:
            detail["stale"].append(inst.symbol)
            continue
        info: dict[str, Any] = {"new_bars": len(new), "outcomes": 0, "signals": [], "rejected": 0}
        expiry = rules.params("three_eight.expiry", inst.id)
        window = rules.params("three_eight.trading_window", inst.id)
        for candle in new:
            bar = BarView(
                candle.ts, float(candle.o), float(candle.h), float(candle.l), float(candle.c)
            )
            for sig in store.open_signals(conn, inst.id, float(inst.pip_size)):
                out = track(
                    sig, bar, bars_since=store.bars_since(sig.bar_ts, candle.ts),
                    three_eight_expiry=expiry if rules.enabled("three_eight.expiry") else None,
                    trading_window=window, window=window["window"],
                )  # fmt: skip
                if out.events or out.state:
                    store.apply_outcome(conn, sig.id, out)
                    info["outcomes"] += 1
            result = evaluate_bar(conn, inst, candle.ts, rules, configs)
            info["signals"] += result["signals"]
            info["rejected"] += result["rejected"]
        detail["instruments"][inst.symbol] = info
    return detail
