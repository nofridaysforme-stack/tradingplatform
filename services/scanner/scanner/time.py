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


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth weekday (0 Monday) of a month; n = -1 for the last."""
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    last = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    n = h + l_ - 7 * m + 114
    return date(year, n // 31, n % 31 + 1)


def _observed(day: date) -> date | None:
    """NYSE observance: Sunday moves to Monday; Saturday moves to Friday, except that a
    Saturday New Year's Day is not observed (NYSE Rule 7.2)."""
    if day.weekday() == 6:
        return day + timedelta(days=1)
    if day.weekday() == 5:
        return None if (day.month, day.day) == (1, 1) else day - timedelta(days=1)
    return day


def us_stock_holidays(year: int) -> set[date]:
    """The NYSE full-day holidays of a year, by the exchange's standing rules. Unscheduled
    closures (a national day of mourning) are added in market_holidays."""
    fixed = [date(year, 1, 1), date(year, 7, 4), date(year, 12, 25)]
    if year >= 2022:
        fixed.append(date(year, 6, 19))
    out = {d for d in map(_observed, fixed) if d is not None}
    out |= {
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday
        _easter(year) - timedelta(days=2),  # Good Friday
        _nth_weekday(year, 5, 0, -1),  # Memorial Day
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
    }
    return out
