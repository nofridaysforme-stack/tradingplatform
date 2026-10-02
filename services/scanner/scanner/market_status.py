"""Forex market status for the portal's status line (spec 13, spec 14 market-status).

The worker computes it with each heartbeat from the same calendar and trading window rule
the strategies use, and stores it in worker_heartbeat.market. The portal only displays it.
"""

from collections.abc import Collection, Mapping
from datetime import date, datetime, timedelta

from pydantic import BaseModel

from scanner.rules.registry import RuleSet
from scanner.strategies.common import BAR, in_window, trading_windows
from scanner.time import (
    is_forex_open,
    is_forex_trading_day,
    require_utc,
    trading_day_of,
    trading_day_start,
)

WINDOW_RULE = "three_eight.trading_window"
STALE_AFTER = timedelta(minutes=30)  # spec 04, data staleness rules


class Window(BaseModel):
    start: str
    end: str


class MarketStatus(BaseModel):
    at: datetime
    forex_open: bool
    trading_day: date
    window_enabled: bool
    window: str  # primary, alternative, or both
    windows: list[Window]
    in_window: bool
    next_open: datetime | None  # set while the market is closed
    stale: list[str]


def market_status(
    now: datetime,
    rules: RuleSet,
    holidays: Collection[date],
    last_bars: Mapping[str, datetime | None],
) -> MarketStatus:
    """last_bars maps each enabled pair to the open time of its newest stored M15 bar."""
    now = require_utc(now)
    day = trading_day_of(now)
    is_open = is_forex_open(now, holidays)
    rule = rules.rule(WINDOW_RULE)
    params = rules.params(WINDOW_RULE)
    windows = [Window(start=s, end=e) for s, e in trading_windows(params, params["window"])]
    inside = is_open and rule.enabled and any(in_window(now, w.start, w.end) for w in windows)
    return MarketStatus(
        at=now,
        forex_open=is_open,
        trading_day=day,
        window_enabled=rule.enabled,
        window=params["window"],
        windows=windows,
        in_window=inside,
        next_open=None if is_open else next_open(day, holidays),
        stale=stale_pairs(now, is_open, trading_day_start(day), last_bars),
    )


def next_open(closed_day: date, holidays: Collection[date]) -> datetime:
    """When forex next opens, from inside a closed trading day."""
    d = closed_day + timedelta(days=1)
    while not is_forex_trading_day(d, holidays):
        d += timedelta(days=1)
    return trading_day_start(d)


def stale_pairs(
    now: datetime,
    is_open: bool,
    opened_at: datetime,
    last_bars: Mapping[str, datetime | None],
) -> list[str]:
    """Pairs with no new completed bar for 30 minutes while the market is open. The clock
    starts at the later of the last bar's close and the trading day's open, so pairs are not
    stale in the first 30 minutes after the weekend."""
    if not is_open:
        return []
    out = []
    for symbol, last in sorted(last_bars.items()):
        since = max(last + BAR, opened_at) if last is not None else opened_at
        if now - since > STALE_AFTER:
            out.append(symbol)
    return out
