"""Health alerts (spec 11): to admins and OPS_ALERT_EMAIL by email and Telegram, at most once
an hour per condition, with a "Resolved" message when it clears."""

import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from scanner import db
from scanner.notify.channels import Sender
from scanner.notify.dispatcher import Planned, enqueue, plan_for, recipients
from scanner.notify.messages import Message, health_message
from scanner.notify.prefs import Channel

HEARTBEAT_LATE = timedelta(minutes=5)
REPEAT = timedelta(hours=1)
FAILS_IN_A_ROW = 3
WATCHED_JOBS = ("forex_bar_close", "forex_day_roll", "stock_eod", "backfill", "ticker_refresh")
PROVIDER_JOBS = {"forex_bar_close": "OANDA", "backfill": "OANDA", "stock_eod": "Massive"}
AUTH_ERROR = re.compile(r"returned (401|403)|paused until")
HEALTH_CHANNELS: tuple[Channel, ...] = ("email", "telegram")


def conditions(conn: db.Conn, now: datetime) -> dict[str, str]:
    """Active conditions and a one-line description of each."""
    out: dict[str, str] = {}
    hb = conn.execute("SELECT at, market FROM worker_heartbeat").fetchone()
    if hb is None or now - hb[0] > HEARTBEAT_LATE:
        out["heartbeat_stale"] = "The scanner has not reported for over 5 minutes."
    market: dict[str, Any] = (hb[1] if hb else None) or {}
    if market.get("forex_open"):
        for symbol in market.get("stale", []):
            out[f"pair_stale:{symbol}"] = (
                f"No new completed bar for {symbol} for 30 minutes while the market is open. "
                "Alerts for this pair are paused until data resumes."
            )
    for job, provider in PROVIDER_JOBS.items():
        row = conn.execute(
            "SELECT detail FROM job_runs WHERE job = %s AND finished_at IS NOT NULL "
            "ORDER BY started_at DESC LIMIT 1",
            (job,),
        ).fetchone()
        error = str((row[0] or {}).get("error", "")) if row else ""
        if AUTH_ERROR.search(error):
            out[f"provider_auth:{provider}"] = f"{provider} rejected the API key ({error})."
    for job in WATCHED_JOBS:
        runs = conn.execute(
            "SELECT ok FROM job_runs WHERE job = %s AND finished_at IS NOT NULL "
            "ORDER BY started_at DESC LIMIT %s",
            (job, FAILS_IN_A_ROW),
        ).fetchall()
        if len(runs) == FAILS_IN_A_ROW and all(r[0] is False for r in runs):
            out[f"job_failing:{job}"] = f"The {job} job failed its last {FAILS_IN_A_ROW} runs."
    return out


def run_health_check(
    conn: db.Conn,
    senders: Mapping[Channel, Sender],
    now: datetime,
    base_url: str,
    ops_email: str | None,
) -> dict[str, list[str]]:
    active = conditions(conn, now)
    alerted: list[str] = []
    resolved: list[str] = []
    with conn.transaction():
        state = {
            r[0]: (r[1], r[2], r[3])
            for r in conn.execute(
                "SELECT condition, first_seen_at, last_sent_at, resolved_at FROM health_alerts "
                "FOR UPDATE"
            ).fetchall()
        }
        for cond, text in active.items():
            first, last, done = state.get(cond, (None, None, None))
            if first is None or done is not None:
                first, last = now, None
                conn.execute(
                    "INSERT INTO health_alerts "
                    "(condition, first_seen_at, last_sent_at, resolved_at, detail) "
                    "VALUES (%s, %s, NULL, NULL, jsonb_build_object('text', %s::text)) "
                    "ON CONFLICT (condition) DO UPDATE SET first_seen_at = EXCLUDED.first_seen_at, "
                    "last_sent_at = NULL, resolved_at = NULL, detail = EXCLUDED.detail",
                    (cond, now, text),
                )
            if last is None or now - last >= REPEAT:
                msg = health_message(cond, text, resolved=False, base_url=base_url)
                _send(conn, msg, f"health:{cond}:{now:%Y%m%dT%H%M}", senders, now, ops_email)
                conn.execute(
                    "UPDATE health_alerts SET last_sent_at = %s WHERE condition = %s", (now, cond)
                )
                alerted.append(cond)
        for cond, (first, last, done) in state.items():
            if done is None and cond not in active:
                conn.execute(
                    "UPDATE health_alerts SET resolved_at = %s WHERE condition = %s", (now, cond)
                )
                if last is not None:
                    msg = health_message(cond, "Back to normal.", resolved=True, base_url=base_url)
                    key = f"health:{cond}:resolved:{first:%Y%m%dT%H%M}"
                    _send(conn, msg, key, senders, now, ops_email)
                resolved.append(cond)
    return {"active": sorted(active), "alerted": alerted, "resolved": resolved}


def _send(
    conn: db.Conn,
    msg: Message,
    key: str,
    senders: Mapping[Channel, Sender],
    now: datetime,
    ops_email: str | None,
) -> None:
    planned: list[Planned] = []
    admins = recipients(conn, admins_only=True)
    for r in admins:
        planned += plan_for(
            r, kind="health", message=msg, dedupe_key=key, now=now, senders=senders,
            channels=HEALTH_CHANNELS,
        )  # fmt: skip
    if ops_email and ops_email.lower() not in {a.email.lower() for a in admins}:
        planned.append(
            Planned(
                None, "email", "health", msg, key,
                "queued" if "email" in senders else "skipped",
                None if "email" in senders else "not_configured", to=ops_email,
            )
        )  # fmt: skip
    enqueue(conn, planned, now)
