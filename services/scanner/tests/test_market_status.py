from datetime import UTC, date, datetime, timedelta
from typing import Any

import psycopg

from scanner import db
from scanner.market_status import market_status, stale_pairs
from scanner.rules.registry import derive
from tests.conftest import ruleset_from_snapshot

RULES = ruleset_from_snapshot()
NOW = datetime(2026, 10, 7, 13, 30, tzinfo=UTC)  # Wednesday 09:30 New York (EDT)
FRESH = {"EUR/USD": NOW - timedelta(minutes=30), "GBP/USD": NOW - timedelta(minutes=15)}


def test_open_and_inside_the_primary_window() -> None:
    s = market_status(NOW, RULES, set(), FRESH)
    assert s.forex_open and s.in_window and s.window_enabled
    assert s.trading_day == date(2026, 10, 7)
    assert s.window == "primary"
    assert [(w.start, w.end) for w in s.windows] == [("00:00", "10:30")]
    assert s.stale == []


def test_outside_the_window_after_it_ends() -> None:
    later = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)  # 11:00 New York
    s = market_status(later, RULES, set(), {})
    assert s.forex_open and not s.in_window


def test_window_follows_the_rule_parameters() -> None:
    later = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
    alt = derive(RULES, {"three_eight.trading_window": {"window": "alternative"}}, set())
    assert market_status(later, alt, set(), {}).in_window


def test_a_disabled_window_rule_is_never_inside() -> None:
    off = derive(RULES, {}, {"three_eight.trading_window"})
    s = market_status(NOW, off, set(), {})
    assert not s.window_enabled and not s.in_window


def test_closed_at_the_weekend_and_on_holidays() -> None:
    saturday = market_status(datetime(2026, 10, 10, 15, 0, tzinfo=UTC), RULES, set(), {})
    assert not saturday.forex_open
    assert saturday.next_open == datetime(2026, 10, 11, 21, 0, tzinfo=UTC)  # Sunday 17:00 NY
    holiday = market_status(NOW, RULES, {date(2026, 10, 7)}, FRESH)
    assert not holiday.forex_open and not holiday.in_window and holiday.stale == []
    assert holiday.next_open == datetime(2026, 10, 7, 21, 0, tzinfo=UTC)  # Wednesday 17:00 NY
    assert market_status(NOW, RULES, set(), FRESH).next_open is None


def test_a_pair_is_stale_after_30_minutes_without_a_new_bar() -> None:
    # The newest bar opened at 08:45 and closed at 09:00 UTC: 30 minutes ago is not stale,
    # 31 minutes ago is.
    last = {"EUR/USD": NOW - timedelta(minutes=45), "USD/JPY": NOW - timedelta(minutes=46)}
    assert market_status(NOW, RULES, set(), last).stale == ["USD/JPY"]


def test_no_pair_is_stale_in_the_first_30_minutes_after_the_weekend() -> None:
    opened = datetime(2026, 10, 4, 21, 0, tzinfo=UTC)  # Sunday 17:00 New York
    friday = {"EUR/USD": datetime(2026, 10, 2, 20, 45, tzinfo=UTC)}
    assert stale_pairs(opened + timedelta(minutes=10), True, opened, friday) == []
    assert stale_pairs(opened + timedelta(minutes=40), True, opened, friday) == ["EUR/USD"]
    assert stale_pairs(opened + timedelta(minutes=40), True, opened, {"NZD/USD": None}) == [
        "NZD/USD"
    ]


def test_heartbeat_stores_the_status(conn: psycopg.Connection[Any]) -> None:
    s = market_status(NOW, RULES, set(), db.last_m15_bars(conn))
    db.heartbeat(conn, "test", s.model_dump(mode="json"))
    row = conn.execute("SELECT version, market FROM worker_heartbeat").fetchone()
    assert row is not None and row[0] == "test"
    assert row[1]["forex_open"] is True and row[1]["window"] == "primary"
    assert set(db.last_m15_bars(conn)) >= {"EUR/USD", "USD/JPY"}
