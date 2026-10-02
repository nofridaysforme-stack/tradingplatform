"""Turn what the worker wrote into notifications (spec 11, "What triggers a notification")."""

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from scanner import db
from scanner.notify.channels import Sender
from scanner.notify.dispatcher import Planned, Recipient, enqueue, plan_for, recipients
from scanner.notify.messages import (
    DigestRow,
    SignalFacts,
    digest_message,
    holding_message,
    signal_message,
    update_message,
)
from scanner.notify.prefs import Channel
from scanner.signals.broker_adjust import adjust
from scanner.strategies.stock_screener import sales_target

CURSOR = "signal_events"
MAX_AGE = timedelta(hours=2)  # an older event is not news any more (outage catch-up)
UPDATE_KINDS = ("confirmed", "reset_reached", "target_hit", "stop_hit", "expired", "ambiguous")


def _cursor(conn: db.Conn) -> int:
    row = conn.execute("SELECT last_id FROM notify_cursor WHERE name = %s", (CURSOR,)).fetchone()
    if row is not None:
        return int(row[0])
    # First run: start from now, never from the whole history.
    start = conn.execute("SELECT coalesce(max(id), 0) FROM signal_events").fetchone()
    last = int(start[0]) if start else 0
    conn.execute("INSERT INTO notify_cursor (name, last_id) VALUES (%s, %s)", (CURSOR, last))
    return last


def dispatch_signal_events(
    conn: db.Conn, senders: Mapping[Channel, Sender], now: datetime, base_url: str
) -> int:
    """New signals and their updates since the last run. Returns rows written."""
    with conn.transaction():
        last = _cursor(conn)
        with conn.cursor(row_factory=dict_row) as cur:
            events = cur.execute(
                "SELECT e.id AS event_id, e.kind, e.at, e.price, s.id, "
                "s.strategy::text AS strategy, s.direction::text AS direction, "
                "s.entry, s.stop, s.target, s.reward_risk, "
                "s.has_provisional, s.result_pips, s.context, s.instrument_id, i.symbol, "
                "i.pip_size, i.display_decimals "
                "FROM signal_events e JOIN signals s ON s.id = e.signal_id "
                "JOIN instruments i ON i.id = s.instrument_id "
                "WHERE e.id > %s ORDER BY e.id LIMIT 500",
                (last,),
            ).fetchall()
        if not events:
            return 0
        people = recipients(conn)
        written = 0
        for ev in events:
            if ev["kind"] not in ("created", *UPDATE_KINDS) or now - ev["at"] > MAX_AGE:
                continue
            for r in people:
                written += enqueue(conn, _plan_event(conn, ev, r, senders, now, base_url), now)
        conn.execute(
            "UPDATE notify_cursor SET last_id = %s, updated_at = %s WHERE name = %s",
            (events[-1]["event_id"], now, CURSOR),
        )
    return written


def _plan_event(
    conn: db.Conn,
    ev: dict[str, Any],
    r: Recipient,
    senders: Mapping[Channel, Sender],
    now: datetime,
    base_url: str,
) -> list[Planned]:
    common: dict[str, Any] = {
        "now": now,
        "senders": senders,
        "strategy": ev["strategy"],
        "instrument_id": ev["instrument_id"],
        "signal_id": ev["id"],
    }
    if ev["kind"] == "created":
        msg = signal_message(_facts(conn, ev, r), base_url)
        return plan_for(r, kind="signal", message=msg, dedupe_key=f"signal:{ev['id']}", **common)
    msg = update_message(
        signal_id=str(ev["id"]), symbol=ev["symbol"], direction=ev["direction"], kind=ev["kind"],
        at=ev["at"], price=float(ev["price"]) if ev["price"] is not None else None,
        decimals=ev["display_decimals"],
        result_pips=float(ev["result_pips"]) if ev["result_pips"] is not None else None,
        base_url=base_url,
    )  # fmt: skip
    return plan_for(r, kind="update", message=msg, dedupe_key=f"event:{ev['event_id']}", **common)


def _facts(conn: db.Conn, ev: dict[str, Any], r: Recipient) -> SignalFacts:
    """The signal as this owner sees it: adjusted for their broker (spec 10)."""
    entry, stop, target = float(ev["entry"]), float(ev["stop"]), float(ev["target"])
    rr = float(ev["reward_risk"])
    broker = None
    if r.broker_id is not None:
        row = conn.execute(
            "SELECT b.name, s.typical_spread_pips FROM brokers b JOIN broker_spreads s "
            "ON s.broker_id = b.id WHERE b.id = %s AND s.instrument_id = %s AND b.active",
            (r.broker_id, ev["instrument_id"]),
        ).fetchone()
        if row is not None:
            a = adjust(
                ev["direction"], entry, stop, target, float(row[1]), float(ev["pip_size"]),
                ev["display_decimals"],
            )  # fmt: skip
            broker, entry, stop, target, rr = row[0], a.entry, a.stop, a.target, a.reward_risk
    names = [
        n
        for (n,) in conn.execute(
            "SELECT d.name FROM signal_indicators i JOIN rule_definitions d ON d.key = i.key "
            "WHERE i.signal_id = %s AND i.fired ORDER BY d.key",
            (ev["id"],),
        ).fetchall()
    ]
    ctx = ev["context"] or {}
    return SignalFacts(
        id=str(ev["id"]), strategy=ev["strategy"], symbol=ev["symbol"],
        direction=ev["direction"], decimals=ev["display_decimals"], entry=entry, stop=stop,
        target=target, reward_risk=rr,
        indicators=names if ev["strategy"] == "three_eight" else [],
        has_provisional=ev["has_provisional"], broker=broker,
        stop_at=ctx.get("stop_at"), target_at=ctx.get("target_at"),
    )  # fmt: skip


def dispatch_digest(
    conn: db.Conn,
    tickers: Sequence[str],
    session: str,
    senders: Mapping[Channel, Sender],
    now: datetime,
    base_url: str,
) -> int:
    """One evening digest of newly confirmed stocks (written by the stock_eod job)."""
    if not tickers:
        return 0
    rows = conn.execute(
        "SELECT ticker, close, apr_20, apr_50 FROM stock_screen_results "
        "WHERE session_date = %s AND ticker = ANY(%s) ORDER BY apr_20 DESC NULLS LAST",
        (session, list(tickers)),
    ).fetchall()
    msg = digest_message(
        [DigestRow(t, float(c), _f(a20), _f(a50)) for t, c, a20, a50 in rows], session, base_url
    )
    with conn.transaction():
        return sum(
            enqueue(
                conn,
                plan_for(
                    r,
                    kind="digest",
                    message=msg,
                    dedupe_key=f"digest:{session}",
                    now=now,
                    senders=senders,
                    strategy="stocks",
                ),
                now,
            )
            for r in recipients(conn)
        )


def dispatch_holdings(
    conn: db.Conn,
    alerts: Sequence[dict[str, Any]],
    session: str,
    senders: Mapping[Channel, Sender],
    now: datetime,
    base_url: str,
) -> int:
    """Holding alerts go to the holding's owner only."""
    written = 0
    with conn.transaction():
        for a in alerts:
            row = conn.execute(
                "SELECT h.user_id, h.ticker, h.purchase_price, h.expected_profit_pct, "
                "h.horizon_sessions, (SELECT c FROM stock_daily_bars b WHERE b.ticker = h.ticker "
                "AND b.session_date = %s) FROM holdings h WHERE h.id = %s",
                (session, a["holding_id"]),
            ).fetchone()
            if row is None or row[5] is None:
                continue
            user_id, ticker, price, pct, horizon, close = row
            target = sales_target(Decimal(price), Decimal(pct), int(horizon)).target
            msg = holding_message(
                ticker=ticker, alert=a["alert"], target=float(target), last_close=float(close),
                horizon=int(horizon), base_url=base_url,
            )  # fmt: skip
            for r in recipients(conn, user_id=UUID(str(user_id))):
                written += enqueue(
                    conn,
                    plan_for(
                        r,
                        kind="holding",
                        message=msg,
                        dedupe_key=f"holding:{a['holding_id']}:{a['alert']}",
                        now=now,
                        senders=senders,
                        strategy="stocks",
                    ),
                    now,
                )
    return written


def _f(v: Decimal | float | None) -> float | None:
    return None if v is None else float(v)
