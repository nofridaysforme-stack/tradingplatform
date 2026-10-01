"""Market time. Store UTC; use New York time only for session logic and display.

The forex trading day rolls at 17:00 New York time. A trading day is named by the date
on which it ends: the Monday trading day runs Sunday 17:00 to Monday 17:00 New York.
"""

from collections.abc import Collection
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
DAY_ROLL = time(17, 0)
_ROLL_SHIFT = timedelta(hours=24 - DAY_ROLL.hour)


def require_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("naive datetime; all timestamps must be timezone aware")
    return ts.astimezone(UTC)


def to_new_york(ts: datetime) -> datetime:
    return require_utc(ts).astimezone(NEW_YORK)


def trading_day_of(ts: datetime) -> date:
    """The New York trading day that contains the instant ts."""
    return (to_new_york(ts) + _ROLL_SHIFT).date()


def trading_day_start(day: date) -> datetime:
    """UTC instant the trading day opens: 17:00 New York on the previous calendar day."""
    return datetime.combine(day - timedelta(days=1), DAY_ROLL, NEW_YORK).astimezone(UTC)


def trading_day_end(day: date) -> datetime:
    return datetime.combine(day, DAY_ROLL, NEW_YORK).astimezone(UTC)


def is_forex_trading_day(day: date, holidays: Collection[date] = ()) -> bool:
    return day.weekday() < 5 and day not in holidays


def is_forex_open(ts: datetime, holidays: Collection[date] = ()) -> bool:
    """Forex trades Sunday 17:00 to Friday 17:00 New York, except configured holidays."""
    return is_forex_trading_day(trading_day_of(ts), holidays)


def previous_forex_trading_day(day: date, holidays: Collection[date] = ()) -> date:
    d = day - timedelta(days=1)
    while not is_forex_trading_day(d, holidays):
        d -= timedelta(days=1)
    return d


def forex_trading_days_back(day: date, count: int, holidays: Collection[date] = ()) -> date:
    """The trading day `count` trading days before `day`."""
    d = day
    for _ in range(count):
        d = previous_forex_trading_day(d, holidays)
    return d


def is_us_stock_session(day: date, holidays: Collection[date] = ()) -> bool:
    return day.weekday() < 5 and day not in holidays


def us_stock_sessions_back(day: date, count: int, holidays: Collection[date] = ()) -> list[date]:
    """The `count` session dates up to and including `day`, newest first."""
    sessions: list[date] = []
    d = day
    while len(sessions) < count:
        if is_us_stock_session(d, holidays):
            sessions.append(d)
        d -= timedelta(days=1)
    return sessions
