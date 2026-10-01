"""Outcome tracking and expiry (spec 10). Pure: the live jobs and the backtester share it.

On each new completed bar, before new candidates are evaluated, every open or confirmed
signal on the instrument is checked against that bar:
- long: the stop is hit when the low reaches it, the target when the high reaches it
  (short: the mirror). Both inside one bar is `ambiguous` and counts as a loss at the stop.
- Fibonacci Pivot: reaching Confirmation moves an open signal to `confirmed`; reaching
  Reset adds a `reset_reached` event.
- Expiry: 3/8 signals after max_bars bars or at the end of the trading window; Fibonacci
  Pivot signals at the 17:00 New York roll. The result is measured at the expiry bar's close.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from scanner.indicators.base import Direction
from scanner.strategies.common import BAR, parse_hhmm, trading_windows
from scanner.time import to_new_york, trading_day_end

State = Literal[
    "open", "confirmed", "target_hit", "stop_hit", "expired", "invalidated", "ambiguous"
]
CLOSED: frozenset[str] = frozenset(
    {"target_hit", "stop_hit", "expired", "invalidated", "ambiguous"}
)


@dataclass
class TrackedSignal:
    id: Any
    strategy: str
    direction: Direction
    state: State
    bar_ts: datetime
    trading_day: date
    entry: float
    stop: float
    target: float
    pip_size: float
    confirmation: float | None = None  # Fibonacci Pivot only
    reset: float | None = None
    reset_reached: bool = False


@dataclass(frozen=True)
class Event:
    kind: str  # confirmed, reset_reached, target_hit, stop_hit, ambiguous, expired
    at: datetime
    price: float
    note: str | None = None


@dataclass
class Outcome:
    events: list[Event] = field(default_factory=list)
    state: State | None = None  # new state, when it changed
    closed_at: datetime | None = None
    exit_price: float | None = None
    result_pips: float | None = None

    @property
    def closed(self) -> bool:
        return self.closed_at is not None


@dataclass(frozen=True)
class BarView:
    ts: datetime  # open time
    o: float
    h: float
    l: float  # noqa: E741
    c: float

    @property
    def close_time(self) -> datetime:
        return self.ts + BAR


def result_pips(direction: Direction, entry: float, exit_price: float, pip_size: float) -> float:
    move = exit_price - entry if direction == "long" else entry - exit_price
    return round(move / pip_size, 2)


def _close(sig: TrackedSignal, out: Outcome, state: State, at: datetime, price: float) -> Outcome:
    out.events.append(Event(state, at, price))
    out.state = state
    out.closed_at = at
    out.exit_price = price
    out.result_pips = result_pips(sig.direction, sig.entry, price, sig.pip_size)
    return out


def track(
    sig: TrackedSignal,
    bar: BarView,
    *,
    bars_since: int,
    three_eight_expiry: dict[str, Any] | None = None,
    trading_window: dict[str, Any] | None = None,
    window: str = "primary",
) -> Outcome:
    """Apply one completed bar after the signal bar. bars_since counts this bar (1 = first)."""
    out = Outcome()
    if sig.state in CLOSED or bar.ts <= sig.bar_ts:
        return out
    at = bar.close_time
    long = sig.direction == "long"

    # Fibonacci Pivot day roll: a bar of the next trading day ends the signal at its open.
    if sig.strategy == "fib_pivot" and bar.ts >= trading_day_end(sig.trading_day):
        return _close(sig, out, "expired", bar.ts, bar.o)

    if sig.strategy == "fib_pivot":
        if sig.state == "open" and _reached(bar, sig.confirmation, long):
            out.events.append(Event("confirmed", at, float(sig.confirmation or 0)))
            out.state = "confirmed"
        if not sig.reset_reached and _reached(bar, sig.reset, long):
            out.events.append(Event("reset_reached", at, float(sig.reset or 0)))

    stop_hit = (bar.l <= sig.stop) if long else (bar.h >= sig.stop)
    target_hit = (bar.h >= sig.target) if long else (bar.l <= sig.target)
    if stop_hit and target_hit:
        return _close(sig, out, "ambiguous", at, sig.stop)  # conservative: a loss
    if stop_hit:
        return _close(sig, out, "stop_hit", at, sig.stop)
    if target_hit:
        return _close(sig, out, "target_hit", at, sig.target)

    if sig.strategy == "three_eight" and three_eight_expiry is not None:
        if bars_since >= int(three_eight_expiry["max_bars"]):
            return _close(sig, out, "expired", at, bar.c)
        if trading_window is not None and _after_window(at, trading_window, window):
            return _close(sig, out, "expired", at, bar.c)
    return out


def _reached(bar: BarView, level: float | None, long: bool) -> bool:
    if level is None:
        return False
    return bar.h >= level if long else bar.l <= level


def _after_window(close_time: datetime, params: dict[str, Any], which: str) -> bool:
    end = max(parse_hhmm(b) for _, b in trading_windows(params, which))
    start = min(parse_hhmm(a) for a, _ in trading_windows(params, which))
    t = to_new_york(close_time).time()
    return t > end or t < start


def expire_at_roll(sig: TrackedSignal, last_close: float, at: datetime) -> Outcome:
    """Day roll job: end a Fibonacci Pivot signal at the 17:00 New York close."""
    if sig.state in CLOSED:
        return Outcome()
    return _close(sig, Outcome(), "expired", at, last_close)
