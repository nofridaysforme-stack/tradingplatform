from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from scanner.backtest.metrics import summarize
from scanner.ops.weekly_review import (
    AlertRow,
    IndicatorHit,
    NoteRow,
    Review,
    RuleInfo,
    SignalRow,
    build,
    forex_days_between,
    load,
    render,
)
from scanner.time import NEW_YORK

Conn = psycopg.Connection[Any]


def ny(y: int, mo: int, d: int, h: int, mi: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=NEW_YORK).astimezone(UTC)


START, END = ny(2026, 11, 1, 17), ny(2026, 11, 8, 17)  # Sunday open to Sunday open
DAY = timedelta(days=1)


def sig(
    i: int, strategy: str, symbol: str, direction: str, state: str, pips: float | None,
    created: datetime, closed: datetime | None = None,
) -> SignalRow:  # fmt: skip
    return SignalRow(f"s{i}", strategy, symbol, direction, state, pips, created, closed)


SIGNALS = [
    sig(1, "three_eight", "EUR/USD", "long", "target_hit", 40.0, START + DAY, START + DAY * 1.2),
    sig(
        2, "three_eight", "EUR/USD", "short", "stop_hit", -20.0, START + DAY * 2, START + DAY * 2.1
    ),
    sig(3, "three_eight", "GBP/USD", "long", "expired", 5.0, START + DAY * 3, START + DAY * 3.5),
    sig(4, "three_eight", "GBP/USD", "long", "invalidated", None, START + DAY * 3, START + DAY * 4),
    sig(5, "fib_pivot", "USD/JPY", "short", "target_hit", 30.0, START + DAY * 4, START + DAY * 4.1),
    sig(6, "fib_pivot", "USD/JPY", "long", "open", None, START + DAY * 4.5),
    # Created the week before, closed this week: counts in outcomes, not in "created".
    sig(7, "three_eight", "EUR/USD", "long", "stop_hit", -25.0, START - DAY, START + DAY * 0.5),
]
HITS = [
    IndicatorHit("s1", "three_eight.thrust_candle", True, True),
    IndicatorHit("s1", "three_eight.pivot_touch", True, False),
    IndicatorHit("s2", "three_eight.thrust_candle", True, True),
    IndicatorHit("s2", "three_eight.pivot_touch", False, False),
    IndicatorHit("s3", "three_eight.thrust_candle", False, True),
    IndicatorHit("s3", "three_eight.pivot_touch", True, False),
    IndicatorHit("s7", "three_eight.pivot_touch", True, False),
    IndicatorHit("s4", "three_eight.thrust_candle", True, True),  # invalidated: left out
]
RULES = {
    "three_eight.thrust_candle": RuleInfo("Thrust candle", "provisional"),
    "three_eight.pivot_touch": RuleInfo("Pivots", "approved"),
}
ALERTS = [AlertRow("u1", "signal", "telegram")] * 6 + [AlertRow("u2", "signal", "email")] * 4
NOTES = [
    NoteRow(START + DAY * 2.2, "note", "three_eight", "EUR/USD", "Entered late, news spike", "a@x"),
    NoteRow(START + DAY * 4, "invalidated", "three_eight", "GBP/USD", "Bad tick", None),
]


def review() -> Review:
    return build(START, END, SIGNALS, HITS, RULES, ALERTS, NOTES)


def test_created_counts_by_strategy_pair_and_direction() -> None:
    r = review()
    assert r.trading_days == 5
    assert {k: dict(v) for k, v in r.created.items()} == {
        ("fib_pivot", "USD/JPY"): {"short": 1, "long": 1},
        ("three_eight", "EUR/USD"): {"long": 1, "short": 1},
        ("three_eight", "GBP/USD"): {"long": 2},
    }
    assert r.open_now == 1


def test_outcomes_use_the_backtest_definitions_and_leave_out_invalidated() -> None:
    r = review()
    te = r.outcomes["three_eight"]
    assert te == summarize([("target_hit", 40.0), ("stop_hit", -20.0), ("expired", 5.0),
                            ("stop_hit", -25.0)])  # fmt: skip
    assert (te.trades, te.wins, te.net_pips, te.expectancy, te.profit_factor) == (
        4, 1, 0.0, 0.0, 1.0,
    )  # fmt: skip
    assert r.invalidated == 1
    assert r.states["three_eight"]["expired"] == 1


def test_indicator_evidence_puts_provisional_rules_first() -> None:
    thrust, pivots = review().indicators
    assert (thrust.name, thrust.status, thrust.fired, thrust.share) == (
        "Thrust candle", "provisional", 2, 0.5,
    )  # fmt: skip
    assert (thrust.when_fired.wins, thrust.when_fired.expectancy) == (1, 10.0)
    assert (pivots.name, pivots.fired, pivots.share) == ("Pivots", 3, 0.75)


def test_alert_volume_per_owner_per_day() -> None:
    r = review()
    assert r.alerts == {"telegram": 6, "email": 4}
    assert r.owners_alerted == 2
    assert "1.0 per owner per trading day across 2 owners" in render(r)


def test_render_reads_as_a_weekly_review() -> None:
    text = render(review())
    assert "Window: Sun Nov 01 17:00 NY to Sun Nov 08 17:00 NY (5 forex trading days)" in text
    assert "6 in total, 1.2 per trading day" in text
    assert "Marked invalid: 1 (left out of the numbers). Still open: 1" in text
    assert "Note (a@x): Entered late, news spike" in text
    assert "Marked invalid: Bad tick" in text
    # Small samples are called out, with how to see everything so far.
    assert "fired fewer than 30 times: Thrust candle" in text
    assert "--since" in text
    assert "—" not in text


def test_an_empty_week() -> None:
    text = render(build(START, END, [], [], {}, [], []))
    assert text.count("  None") == 5


def test_forex_days_count_partly_covered_days() -> None:
    assert forex_days_between(ny(2026, 11, 4, 12), ny(2026, 11, 5, 9)) == 2  # Wed, Thu
    assert forex_days_between(ny(2026, 11, 7, 9), ny(2026, 11, 8, 9)) == 0  # weekend


def test_load_reads_signals_indicators_alerts_and_note_authors(conn: Conn) -> None:
    inst = conn.execute("SELECT id FROM instruments WHERE symbol = 'EUR/USD'").fetchone()
    assert inst is not None
    admin = conn.execute(
        "INSERT INTO users (email, role) VALUES ('review-admin@example.com', 'admin') RETURNING id"
    ).fetchone()
    assert admin is not None
    at = START + DAY
    row = conn.execute(
        "INSERT INTO signals (strategy, instrument_id, direction, state, bar_ts, trading_day, "
        "entry, stop, target, risk_pips, reward_pips, reward_risk, version_set, context, "
        "dedupe_key, closed_at, result_pips, created_at) VALUES ('three_eight', %s, 'long', "
        "'target_hit', %s, %s, 1.1, 1.09, 1.12, 10, 20, 2, %s, %s, 'review-test', %s, 20, %s) "
        "RETURNING id",
        (inst[0], at, at.date(), Jsonb({}), Jsonb({}), at + DAY * 0.2, at),
    ).fetchone()
    assert row is not None
    sid = row[0]
    conn.execute(
        "INSERT INTO signal_indicators (signal_id, key, version, fired, counted, provisional, "
        "detail) VALUES (%s, 'three_eight.thrust_candle', 1, true, true, true, %s)",
        (sid, Jsonb({})),
    )
    conn.execute(
        "INSERT INTO signal_events (signal_id, at, kind, note) VALUES (%s, %s, 'note', 'Late')",
        (sid, at + DAY * 0.3),
    )
    conn.execute(
        "INSERT INTO audit_log (at, user_id, action, target, after) "
        "VALUES (%s, %s, 'signal.note', %s, %s)",
        (at + DAY * 0.3, admin[0], str(sid), Jsonb({"note": "Late"})),
    )
    conn.execute(
        "INSERT INTO notifications (user_id, signal_id, kind, channel, status, payload, sent_at, "
        "created_at) VALUES (%s, %s, 'signal', 'email', 'sent', %s, %s, %s)",
        (admin[0], sid, Jsonb({}), at, at),
    )
    data = load(conn, START, END)
    mine = [s for s in data.signals if s.id == str(sid)]
    assert mine and mine[0].symbol == "EUR/USD" and mine[0].result_pips == 20.0
    assert IndicatorHit(str(sid), "three_eight.thrust_candle", True, True) in data.hits
    assert data.rules["three_eight.thrust_candle"].name == "Thrust candle"
    assert any(a.user_id == str(admin[0]) and a.channel == "email" for a in data.alerts)
    assert [n.author for n in data.notes if n.note == "Late"] == ["review-admin@example.com"]
