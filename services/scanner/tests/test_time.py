from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from scanner.time import (
    forex_trading_days_back,
    is_forex_open,
    previous_forex_trading_day,
    to_new_york,
    trading_day_end,
    trading_day_of,
    trading_day_start,
    us_stock_sessions_back,
)

NY = ZoneInfo("America/New_York")


def ny(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=NY)


@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        (ny(2026, 9, 28, 16, 59), date(2026, 9, 28)),  # Monday before the roll
        (ny(2026, 9, 28, 17, 0), date(2026, 9, 29)),  # Monday 17:00 starts Tuesday
        (ny(2026, 9, 27, 17, 0), date(2026, 9, 28)),  # Sunday open is Monday's trading day
        (ny(2026, 11, 1, 17, 30), date(2026, 11, 2)),  # first evening after DST ends
        (ny(2026, 3, 8, 17, 0), date(2026, 3, 9)),  # first evening after DST starts
    ],
)
def test_trading_day_of(instant: datetime, expected: date) -> None:
    assert trading_day_of(instant) == expected
    assert trading_day_of(instant.astimezone(UTC)) == expected


def test_trading_day_bounds_follow_daylight_saving() -> None:
    # Summer (EDT, UTC-4): opens 21:00 UTC. Winter (EST, UTC-5): opens 22:00 UTC.
    assert trading_day_start(date(2026, 9, 29)) == datetime(2026, 9, 28, 21, tzinfo=UTC)
    assert trading_day_start(date(2026, 12, 1)) == datetime(2026, 11, 30, 22, tzinfo=UTC)
    assert trading_day_end(date(2026, 9, 29)) == datetime(2026, 9, 29, 21, tzinfo=UTC)


def test_forex_week_window() -> None:
    assert not is_forex_open(ny(2026, 9, 27, 16, 59))  # Sunday before the open
    assert is_forex_open(ny(2026, 9, 27, 17, 0))  # Sunday open
    assert is_forex_open(ny(2026, 10, 2, 16, 59))  # Friday before the close
    assert not is_forex_open(ny(2026, 10, 2, 17, 0))  # Friday close
    assert not is_forex_open(ny(2026, 10, 3, 12, 0))  # Saturday


def test_forex_holiday_closes_the_trading_day() -> None:
    christmas = {date(2026, 12, 25)}
    assert not is_forex_open(ny(2026, 12, 25, 9, 0), christmas)
    assert is_forex_open(ny(2026, 12, 25, 9, 0))


def test_previous_trading_day_skips_weekends_and_holidays() -> None:
    assert previous_forex_trading_day(date(2026, 9, 28)) == date(2026, 9, 25)
    assert previous_forex_trading_day(date(2026, 12, 28), {date(2026, 12, 25)}) == date(
        2026, 12, 24
    )
    assert forex_trading_days_back(date(2026, 10, 2), 5) == date(2026, 9, 25)


def test_us_stock_sessions_back() -> None:
    sessions = us_stock_sessions_back(date(2026, 9, 29), 3, {date(2026, 9, 28)})
    assert sessions == [date(2026, 9, 29), date(2026, 9, 25), date(2026, 9, 24)]


def test_naive_datetimes_are_rejected() -> None:
    with pytest.raises(ValueError, match="naive"):
        to_new_york(datetime(2026, 9, 28, 12))  # noqa: DTZ001
