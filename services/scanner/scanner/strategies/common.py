"""Types shared by the strategies, the live jobs, and the backtester."""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from scanner.indicators.base import Bars, Direction
from scanner.rules.registry import RuleSet
from scanner.time import to_new_york

BAR = timedelta(minutes=15)


@dataclass(frozen=True)
class InstrumentRef:
    id: UUID
    symbol: str  # 'EUR/USD'
    pip_size: float
    display_decimals: int

    @property
    def currencies(self) -> tuple[str, str]:
        base, quote = self.symbol.split("/")
        return base, quote


@dataclass(frozen=True)
class EconEvent:
    at: datetime
    currency: str
    impact: Literal["high", "medium", "low"]


@dataclass(frozen=True)
class PriorSignal:
    """A signal already written, as the strategies need it for cooldowns and daily limits."""

    strategy: str
    direction: Direction
    bar_ts: datetime
    trading_day: date
    closed: bool = False
    result_pips: float | None = None


@dataclass(frozen=True)
class Context:
    """Everything a strategy may look at for one completed bar: the last bar in `bars`."""

    instrument: InstrumentRef
    bars: Bars
    trading_day: date
    levels: dict[str, dict[str, Any]]  # stored level sets for the trading day
    rules: RuleSet
    econ_events: list[EconEvent] = field(default_factory=list)
    prior_signals: list[PriorSignal] = field(default_factory=list)

    @property
    def i(self) -> int:
        return len(self.bars) - 1

    @property
    def bar_ts(self) -> datetime:
        return self.bars.ts[self.i]

    @property
    def bar_close_time(self) -> datetime:
        return self.bar_ts + BAR


class IndicatorOut(BaseModel):
    key: str
    name: str
    version: int
    fired: bool
    counted: bool
    provisional: bool
    level_ref: str | None = None
    detail: dict[str, Any] = {}


class GateOut(BaseModel):
    key: str
    passed: bool
    detail: dict[str, Any] = {}


class SignalDraft(BaseModel):
    """A new signal, before it is written. Matches the spec 10 payload."""

    strategy: str
    instrument_id: UUID
    instrument: str
    direction: Direction
    bar_ts: datetime
    trading_day: date
    entry: float
    stop: float
    target: float
    alt_target: float | None = None
    risk_pips: float
    reward_pips: float
    reward_risk: float
    indicator_count: int | None = None
    minimum: int | None = None
    has_provisional: bool = False
    is_countertrend: bool = False
    range_mode: bool = False
    indicators: list[IndicatorOut] = []
    gates: list[GateOut] = []
    version_set: dict[str, int]
    context: dict[str, Any] = {}
    explanation: str
    dedupe_key: str


class Rejection(BaseModel):
    """A candidate that failed a gate. Logged at debug level and counted by the backtester."""

    strategy: str
    direction: Direction
    bar_ts: datetime
    failed: list[str]
    gates: list[GateOut]


class Evaluation(BaseModel):
    signals: list[SignalDraft] = []
    rejections: list[Rejection] = []


def parse_hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def in_window(close_time: datetime, start: str, end: str) -> bool:
    t = to_new_york(close_time).time()
    return parse_hhmm(start) <= t <= parse_hhmm(end)


def trading_windows(params: dict[str, Any], which: str) -> list[tuple[str, str]]:
    """The New York windows for 'primary', 'alternative', or 'both' (rule trading_window)."""
    primary = (params["primary_start"], params["primary_end"])
    alternative = (params["alternative_start"], params["alternative_end"])
    return {"primary": [primary], "alternative": [alternative], "both": [primary, alternative]}[
        which
    ]


def round_price(value: float, decimals: int) -> float:
    return round(value, decimals)


def flip(direction: Direction) -> Direction:
    return "short" if direction == "long" else "long"
