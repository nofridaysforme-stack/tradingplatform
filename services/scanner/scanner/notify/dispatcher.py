"""The dispatcher (spec 11, Delivery).

1. Sources turn events into one notifications row per owner per channel: queued, or skipped
   with the reason (quiet hours, channel not set up, ...). A dedupe key makes each event
   notify once per owner per channel, however often the dispatcher runs.
2. deliver_due sends queued rows concurrently, 10 seconds per call, and retries failures
   up to 3 times at 5, 20, and 60 seconds. Push 404 or 410 deletes the subscription.
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from scanner import db
from scanner.notify.channels import TIMEOUT, DeliveryError, PushSubscription, Sender, Target
from scanner.notify.messages import Message, test_message
from scanner.notify.prefs import CHANNELS, Channel, Kind, Prefs, skip_reason

log = logging.getLogger(__name__)

RETRY_DELAYS = (timedelta(seconds=5), timedelta(seconds=20), timedelta(seconds=60))
BATCH = 100


@dataclass(frozen=True)
class Recipient:
    id: UUID
    email: str
    role: str
    active: bool
    timezone: str
    broker_id: UUID | None
    prefs: Prefs


def recipients(
    conn: db.Conn, *, admins_only: bool = False, user_id: UUID | None = None
) -> list[Recipient]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            "SELECT u.id, u.email, u.role::text AS role, u.active, u.timezone, u.active_broker_id, "
            "p.channels::text[] AS channels, p.strategies::text[] AS strategies, p.instrument_ids, "
            "p.quiet_start, p.quiet_end, p.include_updates "
            "FROM users u LEFT JOIN notification_prefs p ON p.user_id = u.id "
            "WHERE u.active AND (NOT %s OR u.role = 'admin') AND (%s::uuid IS NULL OR u.id = %s) "
            "ORDER BY u.email",
            (admins_only, user_id, user_id),
        ).fetchall()
    out = []
    for r in rows:
        prefs = (
            Prefs()
            if r["channels"] is None
            else Prefs(
                channels=r["channels"],
                strategies=r["strategies"],
                instrument_ids=r["instrument_ids"],
                quiet_start=r["quiet_start"],
                quiet_end=r["quiet_end"],
                include_updates=r["include_updates"],
            )
        )
        out.append(
            Recipient(
                r["id"],
                r["email"],
                r["role"],
                r["active"],
                r["timezone"],
                r["active_broker_id"],
                prefs,
            )
        )
    return out


@dataclass(frozen=True)
class Planned:
    user_id: UUID | None
    channel: Channel
    kind: Kind
    message: Message
    dedupe_key: str
    status: str  # queued or skipped
    error: str | None = None
    signal_id: UUID | None = None
    to: str | None = None  # an address with no user (OPS_ALERT_EMAIL)


def plan_for(
    r: Recipient,
    *,
    kind: Kind,
    message: Message,
    dedupe_key: str,
    now: datetime,
    senders: Mapping[Channel, Sender],
    strategy: str | None = None,
    instrument_id: UUID | None = None,
    signal_id: UUID | None = None,
    channels: Sequence[Channel] = CHANNELS,
) -> list[Planned]:
    """One row per channel the owner has turned on (health also always uses email)."""
    out = []
    for ch in channels:
        reason = skip_reason(
            r.prefs, active=r.active, channel=ch, kind=kind, at=now, timezone=r.timezone,
            strategy=strategy, instrument_id=instrument_id,
        )  # fmt: skip
        if reason == "channel_off":
            continue
        if reason is None and ch not in senders:
            reason = "not_configured"
        out.append(
            Planned(
                r.id, ch, kind, message, dedupe_key,
                "skipped" if reason else "queued", reason, signal_id,
            )
        )  # fmt: skip
    return out


def enqueue(conn: db.Conn, planned: Sequence[Planned], now: datetime) -> int:
    """Insert the rows; an already notified (dedupe_key, user, channel) is left alone."""
    n = 0
    for p in planned:
        payload: dict[str, Any] = {
            "title": p.message.title,
            "body": p.message.body,
            "url": p.message.url,
        }
        if p.to:
            payload["to"] = p.to
        row = conn.execute(
            "INSERT INTO notifications (user_id, signal_id, kind, channel, status, error, payload, "
            "dedupe_key, next_attempt_at, sent_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT DO NOTHING RETURNING id",
            (
                p.user_id, p.signal_id, p.kind, p.channel, p.status, p.error, Jsonb(payload),
                p.dedupe_key, now if p.status == "queued" else None, None,
            ),
        ).fetchone()  # fmt: skip
        n += row is not None
    return n


def _target(conn: db.Conn, user_id: UUID | None, payload: dict[str, Any]) -> Target:
    if user_id is None:
        return Target(email=payload.get("to"))
    subs = conn.execute(
        "SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = %s", (user_id,)
    ).fetchall()
    email = conn.execute("SELECT email FROM users WHERE id = %s", (user_id,)).fetchone()
    chat = conn.execute(
        "SELECT chat_id FROM telegram_links WHERE user_id = %s AND chat_id IS NOT NULL", (user_id,)
    ).fetchone()
    return Target(
        subscriptions=tuple(PushSubscription(*s) for s in subs),
        email=email[0] if email else None,
        chat_id=int(chat[0]) if chat else None,
    )


def deliver_due(
    conn: db.Conn,
    senders: Mapping[Channel, Sender],
    now: datetime,
    *,
    base_url: str = "",
    pool: Callable[[], ThreadPoolExecutor] = lambda: ThreadPoolExecutor(max_workers=8),
) -> dict[str, int]:
    """Send every queued row that is due. Returns counts by outcome."""
    with conn.transaction():
        rows = conn.execute(
            "SELECT id, user_id, kind, channel::text, payload, attempts FROM notifications "
            "WHERE status = 'queued' AND coalesce(next_attempt_at, created_at) <= %s "
            "ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED",
            (now, BATCH),
        ).fetchall()
        if not rows:
            return {}
        jobs: list[tuple[int, Channel, Target, Message, int]] = []
        counts: dict[str, int] = {}
        for nid, user_id, kind, channel, payload, attempts in rows:
            sender = senders.get(channel)
            if sender is None:
                _finish(conn, nid, "skipped", "not_configured", attempts)
                counts["skipped"] = counts.get("skipped", 0) + 1
                continue
            target = _target(conn, user_id, payload)
            missing = sender.ready(target)
            if missing:
                _finish(conn, nid, "skipped", missing, attempts)
                counts["skipped"] = counts.get("skipped", 0) + 1
                continue
            # The portal queues test notifications without text; the worker writes it.
            msg = (
                test_message(channel, base_url)
                if kind == "test" and not payload.get("title")
                else Message(payload["title"], payload["body"], payload.get("url"))
            )
            jobs.append((nid, channel, target, msg, attempts))

        with pool() as ex:
            futures = {ex.submit(senders[ch].send, t, m): (nid, att) for nid, ch, t, m, att in jobs}
            wait(futures, timeout=TIMEOUT * 2)
            for fut, (nid, attempts) in futures.items():
                tries = attempts + 1
                try:
                    result = fut.result(timeout=0)
                    _gone(conn, result.gone)
                    conn.execute(
                        "UPDATE notifications SET status = 'sent', attempts = %s, sent_at = %s, "
                        "error = NULL, next_attempt_at = NULL WHERE id = %s",
                        (tries, now, nid),
                    )
                    counts["sent"] = counts.get("sent", 0) + 1
                except DeliveryError as exc:
                    _gone(conn, exc.gone)
                    outcome = _retry_or_fail(conn, nid, tries, str(exc), exc.permanent, now)
                    counts[outcome] = counts.get(outcome, 0) + 1
                except Exception as exc:  # timeouts and anything unexpected
                    outcome = _retry_or_fail(
                        conn, nid, tries, f"send failed: {type(exc).__name__}", False, now
                    )
                    counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def _retry_or_fail(
    conn: db.Conn, nid: int, tries: int, error: str, permanent: bool, now: datetime
) -> str:
    if not permanent and tries <= len(RETRY_DELAYS):
        conn.execute(
            "UPDATE notifications SET attempts = %s, error = %s, next_attempt_at = %s "
            "WHERE id = %s",
            (tries, error, now + RETRY_DELAYS[tries - 1], nid),
        )
        return "retrying"
    _finish(conn, nid, "failed", error, tries)
    return "failed"


def _finish(conn: db.Conn, nid: int, status: str, error: str | None, attempts: int) -> None:
    conn.execute(
        "UPDATE notifications SET status = %s, error = %s, attempts = %s, next_attempt_at = NULL "
        "WHERE id = %s",
        (status, error, attempts, nid),
    )


def _gone(conn: db.Conn, endpoints: Sequence[str]) -> None:
    for e in endpoints:
        conn.execute("DELETE FROM push_subscriptions WHERE endpoint = %s", (e,))
