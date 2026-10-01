"""Build and store every level set for one instrument and New York trading day.

Levels for trading day T come from completed candles that closed before T opened:
- daily floor pivots, previous day, and the Fib Pivot ladder: the daily candle of the
  previous trading day
- weekly pivots: the last weekly candle that opened before T's week
- monthly pivots: the last monthly candle that opened before T's month
"""

from collections.abc import Collection
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from scanner import db
from scanner.data.base import Candle
from scanner.instruments import Instrument
from scanner.levels.fib_pivot import fib_pivot_ladder
from scanner.levels.floor_pivots import floor_pivots
from scanner.levels.prev_day import prev_day
from scanner.time import previous_forex_trading_day, trading_day_start


def _num(values: dict[str, Decimal]) -> dict[str, float]:
    return {k: db.decimal_json(v) for k, v in values.items()}


def _source(candle: Candle) -> dict[str, Any]:
    return {
        "granularity": candle.granularity,
        "ts": candle.ts.isoformat(),
        "h": db.decimal_json(candle.h),
        "l": db.decimal_json(candle.l),
        "c": db.decimal_json(candle.c),
    }


def build_levels(
    instrument: Instrument,
    *,
    daily: Candle | None,
    weekly: Candle | None,
    monthly: Candle | None,
    fib_params: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Pure: source candles in, level sets out (keyed by the level_set enum)."""
    out: dict[str, dict[str, Any]] = {}
    if daily is not None:
        out["daily"] = {**_num(floor_pivots(daily.h, daily.l, daily.c)), "source": _source(daily)}
        out["prev_day"] = {**_num(prev_day(daily.h, daily.l, daily.c)), "source": _source(daily)}
        if fib_params.get("forex_unit", "pip") != "pip":
            raise ValueError(f"unsupported fib_pivot unit {fib_params.get('forex_unit')}")
        ladder = fib_pivot_ladder(
            daily.h,
            daily.l,
            daily.c,
            instrument.pip_size,
            min_fib=int(fib_params["min_fib"]),
            max_fib=int(fib_params["max_fib"]),
        )
        out["fib_pivot"] = {
            "pivot": db.decimal_json(ladder.pivot),
            "range_units": float(ladder.range_units.quantize(Decimal("0.01"))),
            "fib": ladder.fib,
            "offsets": ladder.offsets,
            "unit": db.decimal_json(ladder.unit),
            "up": _num(ladder.up),
            "down": _num(ladder.down),
            "source": _source(daily),
        }
    if weekly is not None:
        out["weekly"] = {
            **_num(floor_pivots(weekly.h, weekly.l, weekly.c)),
            "source": _source(weekly),
        }
    if monthly is not None:
        out["monthly"] = {
            **_num(floor_pivots(monthly.h, monthly.l, monthly.c)),
            "source": _source(monthly),
        }
    return out


def compute_and_store(
    conn: db.Conn,
    instrument: Instrument,
    trading_day: date,
    holidays: Collection[date] = (),
) -> dict[str, dict[str, Any]]:
    prior = previous_forex_trading_day(trading_day, holidays)
    daily = db.candle_at(conn, instrument.id, "D", trading_day_start(prior))
    monday = trading_day - timedelta(days=trading_day.weekday())
    weekly = db.last_candle_before(conn, instrument.id, "W", trading_day_start(monday))
    first_of_month = trading_day.replace(day=1)
    monthly = db.last_candle_before(conn, instrument.id, "M", trading_day_start(first_of_month))

    fib_params = {
        **db.rule_params(conn, "fib_pivot.unit", instrument.id),
        **db.rule_params(conn, "fib_pivot.levels", instrument.id),
    }
    sets = build_levels(
        instrument, daily=daily, weekly=weekly, monthly=monthly, fib_params=fib_params
    )
    with conn.transaction():
        for kind, data in sets.items():
            db.upsert_levels(conn, instrument.id, trading_day, kind, data)
    return sets
