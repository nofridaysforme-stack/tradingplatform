"""forex_day_roll (spec 03): 17:01 New York, Sunday to Friday. Store the completed daily,
weekly, and monthly candles, compute the new trading day's levels, and expire Fibonacci
Pivot signals from the day that just ended."""

import logging
from datetime import datetime
from typing import Any

from scanner import db
from scanner.data.base import completed
from scanner.jobs.forex_bar_close import CandleSource
from scanner.levels.compute import compute_and_store
from scanner.rules.registry import Registry
from scanner.signals import store
from scanner.signals.lifecycle import expire_at_roll
from scanner.time import trading_day_end, trading_day_of

log = logging.getLogger(__name__)


def run(conn: db.Conn, source: CandleSource, registry: Registry, now: datetime) -> dict[str, Any]:
    registry.refresh(conn)
    rules = registry.ruleset
    holidays = db.holidays(conn, "forex")
    day = trading_day_of(now)
    detail: dict[str, Any] = {"trading_day": day.isoformat(), "instruments": {}}
    for inst in db.list_instruments(conn):
        stored = 0
        for gran in ("D", "W", "M"):
            fresh = completed(source.candles(inst.provider_code, gran, count=3))
            with conn.transaction():
                stored += db.upsert_candles(conn, inst.id, fresh)
        sets = compute_and_store(conn, inst, day, holidays)

        expired = 0
        if (
            rules.enabled("fib_pivot.expiry")
            and rules.params("fib_pivot.expiry", inst.id)["expire_at_day_roll"]
        ):
            last = db.recent_candles(conn, inst.id, "M15", now, 1)
            for sig in store.open_signals(conn, inst.id, float(inst.pip_size)):
                if sig.strategy == "fib_pivot" and sig.trading_day < day and last:
                    store.apply_outcome(
                        conn,
                        sig.id,
                        expire_at_roll(sig, last[-1][4], trading_day_end(sig.trading_day)),
                    )
                    expired += 1
        detail["instruments"][inst.symbol] = {
            "candles": stored, "level_sets": sorted(sets), "expired": expired,
        }  # fmt: skip
        if "daily" not in sets:
            log.warning("daily levels missing", extra={"instrument": inst.symbol, "day": str(day)})
    return detail
