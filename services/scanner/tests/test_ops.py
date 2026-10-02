import base64
from datetime import UTC, date, datetime, timedelta

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid  # type: ignore[import-untyped]

from scanner.ops import vapid_keys
from scanner.ops.staging_report import (
    DeliveryCheck,
    HealthAlert,
    Run,
    bar_slots,
    build,
    complete_trading_days,
    failed_runs,
    missed_slots,
    outages,
    render,
    window,
)
from scanner.time import NEW_YORK

M15 = timedelta(minutes=15)


def ny(y: int, mo: int, d: int, h: int, mi: int) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=NEW_YORK).astimezone(UTC)


def every_slot(
    start: datetime, end: datetime, delay: timedelta = timedelta(seconds=5)
) -> list[Run]:
    """A bar close run every 15 minutes, as the scheduler makes, open market or not."""
    runs: list[Run] = []
    t = start
    while t < end:
        runs.append(Run("forex_bar_close", t + delay, t + delay + timedelta(seconds=3), True))
        t += M15
    return runs


def test_bar_slots_follow_the_market_over_a_weekend() -> None:
    slots = bar_slots(ny(2026, 10, 9, 16, 0), ny(2026, 10, 11, 18, 0))
    # Friday's last bar closes at 17:00; Sunday's first completes at 17:15.
    assert [s.astimezone(NEW_YORK).strftime("%a %H:%M") for s in slots] == [
        "Fri 16:00", "Fri 16:15", "Fri 16:30", "Fri 16:45", "Fri 17:00",
        "Sun 17:15", "Sun 17:30", "Sun 17:45",
    ]  # fmt: skip


def test_bar_slots_skip_holidays() -> None:
    slots = bar_slots(ny(2026, 12, 24, 17, 15), ny(2026, 12, 25, 17, 0), {date(2026, 12, 25)})
    assert slots == []


def test_a_retry_inside_the_slot_counts_and_a_failure_alone_does_not() -> None:
    start = ny(2026, 10, 6, 9, 0)
    slots = [start, start + M15, start + 2 * M15]
    runs = [
        Run("forex_bar_close", start + timedelta(seconds=5), start, False),
        Run("forex_bar_close", start + timedelta(seconds=45), start, True),  # retry
        Run("forex_bar_close", start + M15 + timedelta(seconds=5), start, False),
        Run("forex_day_roll", start + 2 * M15, start, True),  # another job
    ]
    assert missed_slots(slots, runs) == [start + M15, start + 2 * M15]


def test_outages_are_gaps_between_runs_including_the_edges() -> None:
    start, end = ny(2026, 10, 6, 9, 0), ny(2026, 10, 6, 12, 0)
    runs = [
        r
        for r in every_slot(start, end)
        if not ny(2026, 10, 6, 10, 0) <= r.started_at < ny(2026, 10, 6, 10, 30)
    ]
    gaps = outages(runs, start, end)
    assert len(gaps) == 1
    assert gaps[0][1] - gaps[0][0] == timedelta(minutes=45)
    assert outages([], start, end) == [(start, end)]


def test_failed_and_unfinished_runs() -> None:
    now = ny(2026, 10, 6, 12, 0)
    runs = [
        Run("stock_eod", now - timedelta(hours=2), now, False, "Massive returned 401"),
        Run("forex_bar_close", now - timedelta(hours=1), None, None),  # died mid-run
        Run("forex_bar_close", now - timedelta(minutes=2), None, None),  # still running
        Run("forex_bar_close", now - timedelta(minutes=30), now, True),
    ]
    assert [r.started_at for r in failed_runs(runs, now)] == [
        runs[0].started_at,
        runs[1].started_at,
    ]


def test_complete_trading_days_and_the_default_window() -> None:
    saturday = ny(2026, 10, 17, 10, 0)
    start, end = window(saturday, 10, None, set())
    assert start == ny(2026, 10, 4, 17, 0)  # Monday Oct 5 opens Sunday 17:00
    days = complete_trading_days(start, end)
    assert days[0] == date(2026, 10, 5) and days[-1] == date(2026, 10, 16) and len(days) == 10
    # Mid-week the day in progress is left out.
    wed_start, _ = window(ny(2026, 10, 14, 12, 0), 2, None, set())
    assert wed_start == ny(2026, 10, 11, 17, 0)
    assert window(saturday, 10, date(2026, 10, 7), set())[0] == ny(2026, 10, 6, 17, 0)


def clean_run() -> tuple[datetime, datetime, list[Run], list[DeliveryCheck]]:
    start, end = ny(2026, 10, 4, 17, 0), ny(2026, 10, 17, 10, 0)
    at = start + timedelta(days=1)
    tests = [
        DeliveryCheck("a@example.com", "email", "sent", at, at + timedelta(seconds=12)),
        DeliveryCheck("a@example.com", "telegram", "sent", at, at + timedelta(seconds=11)),
    ]
    return start, end, every_slot(start, end), tests


def test_a_clean_ten_day_run_passes() -> None:
    start, end, runs, tests = clean_run()
    report = build(start, end, runs, tests, [])
    assert report.passed, render(report)
    assert report.bar_slots == 10 * 96
    assert "Result: all automatic checks passed" in render(report)


def test_a_missed_bar_a_slow_test_and_an_alert_fail_with_details() -> None:
    start, end, runs, tests = clean_run()
    gone = ny(2026, 10, 7, 9, 30)
    runs = [r for r in runs if not gone <= r.started_at < gone + M15]
    at = start + timedelta(days=2)
    tests.append(DeliveryCheck("b@example.com", "push", "sent", at, at + timedelta(seconds=91)))
    alert = HealthAlert("heartbeat_stale", gone, gone, gone + timedelta(minutes=12))
    report = build(start, end, runs, tests, [alert])
    assert not report.passed
    failing = {name for name, ok, _ in report.checks if not ok}
    # One missing run is also a 30 minute gap in the scanner's runs.
    assert failing == {
        "No missed bar closes",
        "Scanner never down",
        "Test notifications within 90 seconds",
    }
    text = render(report)
    assert "  Wed Oct 07 09:30 NY (1 bar close)" in text
    assert "b@example.com by push: 91 s" in text
    assert "heartbeat_stale: first seen Wed Oct 07 09:30 NY, resolved Wed Oct 07 09:42 NY" in text
    assert "Result: not ready" in text


def test_without_oanda_or_tests_the_report_says_what_to_do() -> None:
    start, end = ny(2026, 10, 4, 17, 0), ny(2026, 10, 17, 10, 0)
    report = build(start, end, [], [], [], oanda_configured=False)
    assert not report.passed
    text = render(report)
    # A long outage is one line per stretch, not one per bar.
    assert "Sun Oct 04 17:15 NY to Fri Oct 09 17:00 NY (480 bar closes)" in text
    assert "OANDA_API_TOKEN is not set" in text
    assert "Send test notification" in text


def b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def test_vapid_keys_work_with_the_push_library() -> None:
    public, private = vapid_keys.generate()
    assert len(b64url_decode(public)) == 65 and b64url_decode(public)[0] == 4
    assert len(b64url_decode(private)) == 32
    v = Vapid.from_string(private)
    derived = v.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    assert derived == b64url_decode(public)
    assert vapid_keys.generate() != (public, private)
