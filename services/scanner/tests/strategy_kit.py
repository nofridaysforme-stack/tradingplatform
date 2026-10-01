"""Turn a strategy fixture file into a Context."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from scanner.indicators.base import Bars
from scanner.rules.registry import RuleSet
from scanner.strategies.common import Context, EconEvent, InstrumentRef, PriorSignal
from tests.conftest import ruleset_from_snapshot

FIXED_ID = UUID("00000000-0000-0000-0000-0000000000e1")


def context(
    fx: dict[str, Any],
    bars_key: list[list[Any]] | None = None,
    rules: RuleSet | None = None,
    prior: list[PriorSignal] | None = None,
) -> Context:
    inst = fx["instrument"]
    rows = bars_key if bars_key is not None else fx["bars"]
    bars = Bars.from_rows(
        [
            (datetime.fromisoformat(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]))
            for r in rows
        ]
    )
    return Context(
        instrument=InstrumentRef(
            FIXED_ID, inst["symbol"], inst["pip_size"], inst["display_decimals"]
        ),
        bars=bars,
        trading_day=date.fromisoformat(fx["trading_day"]),
        levels=fx["levels"],
        rules=rules or ruleset_from_snapshot(),
        econ_events=[
            EconEvent(datetime.fromisoformat(e["at"]), e["currency"], e["impact"])
            for e in fx.get("econ_events", [])
        ],
        prior_signals=prior or [],
    )
