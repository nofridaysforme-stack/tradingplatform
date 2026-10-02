from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from scanner.notify.channels import DeliveryError, SendResult, Target
from scanner.notify.dispatcher import deliver_due
from scanner.notify.health import run_health_check
from scanner.notify.messages import Message
from scanner.notify.prefs import Channel
from scanner.notify.sources import dispatch_digest, dispatch_holdings, dispatch_signal_events

Conn = psycopg.Connection[Any]
BASE = "https://desk.example.com"
NOW = datetime(2026, 10, 7, 14, 0, tzinfo=UTC)  # 10:00 New York


@dataclass
class FakeSender:
    """Records what it would send. fail lists errors to raise, one per call, in order."""

    needs: str
    fail: list[DeliveryError] = field(default_factory=list)
    sent: list[tuple[Target, Message]] = field(default_factory=list)

    def ready(self, target: Target) -> str | None:
        ok = {"webpush": bool(target.subscriptions), "email": bool(target.email),
              "telegram": bool(target.chat_id)}[self.needs]  # fmt: skip
        return None if ok else f"no_{self.needs}"

    def send(self, target: Target, message: Message) -> SendResult:
        if self.fail:
            raise self.fail.pop(0)
        self.sent.append((target, message))
        return SendResult()


@pytest.fixture
def senders() -> dict[Channel, FakeSender]:
    return {c: FakeSender(c) for c in ("webpush", "email", "telegram")}


@pytest.fixture
def people(conn: Conn) -> Iterator[dict[str, UUID]]:
    """Owner A (defaults, push + email), owner B (Telegram only, no updates), admin C."""
    conn.execute("UPDATE users SET active = false")  # only these three, inside the rollback
    ids: dict[str, UUID] = {}
    for name, role in (("a", "owner"), ("b", "owner"), ("c", "admin")):
        row = conn.execute(
            "INSERT INTO users (email, role) VALUES (%s, %s) RETURNING id",
            (f"{name}@example.com", role),
        ).fetchone()
        assert row is not None
        ids[name] = row[0]
    conn.execute(
        "INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth) "
        "VALUES (%s, 'https://push/a', 'k', 'x')",
        (ids["a"],),
    )
    conn.execute(
        "INSERT INTO notification_prefs (user_id, channels, include_updates) "
        "VALUES (%s, '{telegram}', false)",
        (ids["b"],),
    )
    conn.execute("INSERT INTO telegram_links (user_id, chat_id) VALUES (%s, 42)", (ids["b"],))
    broker = conn.execute(
        "INSERT INTO brokers (name) VALUES ('Test broker') RETURNING id"
    ).fetchone()
    assert broker is not None
    conn.execute(
        "INSERT INTO broker_spreads (broker_id, instrument_id, typical_spread_pips) "
        "SELECT %s, id, 1.0 FROM instruments WHERE symbol = 'EUR/USD'",
        (broker[0],),
    )
    conn.execute("UPDATE users SET active_broker_id = %s WHERE id = %s", (broker[0], ids["a"]))
    yield ids


def add_signal(conn: Conn, at: datetime, key: str = "t1") -> UUID:
    row = conn.execute(
        "INSERT INTO signals (strategy, instrument_id, direction, state, bar_ts, trading_day, "
        "entry, stop, target, risk_pips, reward_pips, reward_risk, indicator_count, "
        "has_provisional, version_set, context, dedupe_key) "
        "SELECT 'three_eight', id, 'long', 'open', %s, %s, "
        "1.0842, 1.0819, 1.0905, 23, 63, 2.739, 3, true, '{}', '{}', %s "
        "FROM instruments WHERE symbol = 'EUR/USD' RETURNING id",
        (at - timedelta(minutes=15), at.date(), key),
    ).fetchone()
    assert row is not None
    conn.execute(
        "INSERT INTO signal_indicators "
        "(signal_id, key, version, fired, counted, provisional, detail) "
        "VALUES (%s, 'three_eight.pivot_touch', 1, true, true, false, '{}')",
        (row[0],),
    )
    conn.execute(
        "INSERT INTO signal_events (signal_id, at, kind, price) VALUES (%s, %s, 'created', 1.0842)",
        (row[0], at),
    )
    return UUID(str(row[0]))


def rows(conn: Conn, kind: str | None = None) -> list[tuple[str, str, str, str | None]]:
    return [
        (email or "ops", ch, st, err)
        for email, ch, st, err in conn.execute(
            "SELECT u.email, n.channel::text, n.status::text, n.error FROM notifications n "
            "LEFT JOIN users u ON u.id = n.user_id WHERE %s::text IS NULL OR n.kind = %s "
            "ORDER BY u.email NULLS LAST, n.channel",
            (kind, kind),
        ).fetchall()
    ]


def test_signal_fans_out_per_owner_and_channel(
    conn: Conn, people: dict[str, UUID], senders: dict[Channel, FakeSender]
) -> None:
    assert dispatch_signal_events(conn, senders, NOW, BASE) == 0  # first run starts the cursor
    add_signal(conn, NOW)
    assert dispatch_signal_events(conn, senders, NOW, BASE) == 5
    assert rows(conn, "signal") == [
        ("a@example.com", "webpush", "queued", None),
        ("a@example.com", "email", "queued", None),
        ("b@example.com", "telegram", "queued", None),
        ("c@example.com", "webpush", "queued", None),
        ("c@example.com", "email", "queued", None),
    ]
    assert dispatch_signal_events(conn, senders, NOW, BASE) == 0  # read once

    counts = deliver_due(conn, senders, NOW, base_url=BASE)
    assert counts == {"sent": 4, "skipped": 1}  # C has no push subscription
    a_push = senders["webpush"].sent[0][1]
    assert a_push.title == "Long EUR/USD (3/8 Formula)"
    assert "Entry 1.08425  Stop 1.08185  Target 1.09045" in a_push.body
    assert "Prices adjusted for Test broker." in a_push.body
    assert "Includes a provisional rule." in a_push.body
    c_email = next(m for t, m in senders["email"].sent if t.email == "c@example.com")
    assert "Reference prices." in c_email.body
    assert senders["telegram"].sent[0][0].chat_id == 42


def test_quiet_hours_updates_and_stale_events(
    conn: Conn, people: dict[str, UUID], senders: dict[Channel, FakeSender]
) -> None:
    conn.execute(
        "UPDATE notification_prefs SET quiet_start = '09:00', quiet_end = '11:00' "
        "WHERE user_id = %s",
        (people["b"],),
    )
    dispatch_signal_events(conn, senders, NOW, BASE)
    sid = add_signal(conn, NOW)
    add_signal(conn, NOW - timedelta(hours=3), key="old")  # outage catch-up: not sent
    conn.execute(
        "INSERT INTO signal_events (signal_id, at, kind, price) "
        "VALUES (%s, %s, 'target_hit', 1.0905)",
        (sid, NOW),
    )
    conn.execute("UPDATE signals SET result_pips = 63 WHERE id = %s", (sid,))
    dispatch_signal_events(conn, senders, NOW, BASE)
    assert ("b@example.com", "telegram", "skipped", "quiet_hours") in rows(conn, "signal")
    assert len(rows(conn, "signal")) == 5
    assert ("b@example.com", "telegram", "skipped", "updates_off") in rows(conn, "update")
    deliver_due(conn, senders, NOW, base_url=BASE)
    titles = {m.title for _, m in senders["email"].sent}
    assert "EUR/USD long hit target" in titles


def test_retries_then_gives_up(
    conn: Conn, people: dict[str, UUID], senders: dict[Channel, FakeSender]
) -> None:
    senders["telegram"].fail = [DeliveryError("telegram returned 502")] * 2
    senders["email"].fail = [DeliveryError("email failed")] * 4
    senders["webpush"].fail = [DeliveryError("gone", permanent=True, gone=["https://push/a"])]
    dispatch_signal_events(conn, senders, NOW, BASE)
    add_signal(conn, NOW)
    dispatch_signal_events(conn, senders, NOW, BASE)
    conn.execute("DELETE FROM notifications WHERE user_id = %s", (people["c"],))

    deliver_due(conn, senders, NOW, base_url=BASE)
    # Push 410: subscription removed, no retry.
    assert conn.execute(
        "SELECT count(*) FROM push_subscriptions WHERE user_id = %s", (people["a"],)
    ).fetchone() == (0,)
    assert ("a@example.com", "webpush", "failed", "gone") in rows(conn)
    assert (
        deliver_due(conn, senders, NOW + timedelta(seconds=4), base_url=BASE) == {}
    )  # not due yet
    deliver_due(conn, senders, NOW + timedelta(seconds=5), base_url=BASE)  # retry 1
    deliver_due(conn, senders, NOW + timedelta(seconds=26), base_url=BASE)  # retry 2: telegram sent
    assert ("b@example.com", "telegram", "sent", None) in rows(conn)
    deliver_due(conn, senders, NOW + timedelta(seconds=90), base_url=BASE)  # retry 3: email fails
    assert ("a@example.com", "email", "failed", "email failed") in rows(conn)
    attempts = conn.execute(
        "SELECT attempts FROM notifications WHERE channel = 'email' AND user_id = %s",
        (people["a"],),
    ).fetchone()
    assert attempts == (4,)


def test_queued_test_notification_gets_its_text(
    conn: Conn, people: dict[str, UUID], senders: dict[Channel, FakeSender]
) -> None:
    conn.execute(
        "INSERT INTO notifications (user_id, kind, channel, payload, next_attempt_at) "
        "VALUES (%s, 'test', 'telegram', '{}', %s)",
        (people["b"], NOW),
    )
    assert deliver_due(conn, senders, NOW, base_url=BASE) == {"sent": 1}
    msg = senders["telegram"].sent[0][1]
    assert (msg.title, msg.body, msg.url) == (
        "Test notification", "Notifications reach you on Telegram.", f"{BASE}/settings",
    )  # fmt: skip


def test_digest_and_holdings(
    conn: Conn, people: dict[str, UUID], senders: dict[Channel, FakeSender]
) -> None:
    conn.execute(
        "INSERT INTO stock_screen_results (session_date, ticker, status, close, high_52w, low_52w, "
        "apr_52w, apr_20, apr_50, version_set) VALUES "
        "('2026-10-06', 'AAA', 'trend_confirmed', 12.5, 13, 6, 1.1, 2.039, 1.1, '{}')"
    )
    conn.execute(
        "UPDATE notification_prefs SET strategies = '{three_eight}' WHERE user_id = %s",
        (people["b"],),
    )
    dispatch_digest(conn, ["AAA"], "2026-10-06", senders, NOW, BASE)
    digest = rows(conn, "digest")
    assert {r[0] for r in digest if r[2] == "queued"} == {"a@example.com", "c@example.com"}
    assert ("b@example.com", "telegram", "skipped", "strategy_off") in digest
    assert dispatch_digest(conn, ["AAA"], "2026-10-06", senders, NOW, BASE) == 0  # once per session

    conn.execute(
        "INSERT INTO stock_daily_bars (ticker, session_date, o, h, l, c, volume) "
        "VALUES ('AAA', '2026-10-06', 12, 31, 11, 30.2, 1000)"
    )
    holding = conn.execute(
        "INSERT INTO holdings (user_id, ticker, purchase_price, purchase_date) "
        "VALUES (%s, 'AAA', 23.13, '2026-09-01') RETURNING id",
        (people["a"],),
    ).fetchone()
    assert holding is not None
    dispatch_holdings(
        conn,
        [{"holding_id": str(holding[0]), "alert": "target_reached"}],
        "2026-10-06",
        senders,
        NOW,
        BASE,
    )
    assert {r[0] for r in rows(conn, "holding")} == {"a@example.com"}
    deliver_due(conn, senders, NOW, base_url=BASE)
    titles = [m.title for _, m in senders["email"].sent]
    assert "1 stock confirmed its trend today" in titles
    assert "AAA reached its sales target" in titles


def test_health_alerts_repeat_hourly_and_resolve(
    conn: Conn, people: dict[str, UUID], senders: dict[Channel, FakeSender]
) -> None:
    conn.execute("DELETE FROM worker_heartbeat")
    conn.execute("DELETE FROM health_alerts")
    first = run_health_check(conn, senders, NOW, BASE, "ops@example.com")
    assert first["alerted"] == ["heartbeat_stale"]
    # Admin C by email (always) and the ops address; owners get nothing.
    assert rows(conn, "health") == [
        ("c@example.com", "email", "queued", None),
        ("ops", "email", "queued", None),
    ]
    assert (
        run_health_check(conn, senders, NOW + timedelta(minutes=30), BASE, "ops@example.com")[
            "alerted"
        ]
        == []
    )
    assert run_health_check(conn, senders, NOW + timedelta(minutes=61), BASE, "ops@example.com")[
        "alerted"
    ] == ["heartbeat_stale"]
    market = {"forex_open": True, "stale": ["GBP/USD"]}
    conn.execute(
        "INSERT INTO worker_heartbeat (id, at, version, market) VALUES (true, %s, 't', %s)",
        (NOW + timedelta(minutes=70), Jsonb(market)),
    )
    later = run_health_check(conn, senders, NOW + timedelta(minutes=71), BASE, None)
    assert later["resolved"] == ["heartbeat_stale"]
    assert later["alerted"] == ["pair_stale:GBP/USD"]
    deliver_due(conn, senders, NOW + timedelta(minutes=72), base_url=BASE)
    titles = [m.title for _, m in senders["email"].sent]
    assert "Resolved: scanner heartbeat is late" in titles
    assert "Health alert: no new bars for GBP/USD" in titles


def test_health_conditions_from_job_runs(
    conn: Conn, people: dict[str, UUID], senders: dict[Channel, FakeSender]
) -> None:
    conn.execute("DELETE FROM health_alerts")
    conn.execute(
        "INSERT INTO worker_heartbeat (id, at) VALUES (true, %s) "
        "ON CONFLICT (id) DO UPDATE SET at = %s, market = NULL",
        (NOW, NOW),
    )
    for i in range(3):
        conn.execute(
            "INSERT INTO job_runs (job, started_at, finished_at, ok, detail) VALUES "
            "('forex_bar_close', %s, %s, false, %s)",
            (
                NOW - timedelta(minutes=i),
                NOW - timedelta(minutes=i),
                Jsonb({"error": "oanda returned 401"}),
            ),
        )
    out = run_health_check(conn, senders, NOW, BASE, None)
    assert out["active"] == ["job_failing:forex_bar_close", "provider_auth:OANDA"]
