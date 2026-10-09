"""Turn what the worker wrote into notifications (spec 11, "What triggers a notification")."""

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from scanner import db
from scanner.notify.channels import Sender
from scanner.notify.dispatcher import Planned, Recipient, enqueue, plan_for, recipients
from scanner.notify.messages import (
    INDICATOR_NAMES,
    SELL_NAMES,
    Message,
    SignalFacts,
    StockBuy,
    WatchRow,
    signal_message,
    stock_buy_message,
    stock_exit_message,
    stock_update_message,
    update_message,
    watch_message,
)
from scanner.notify.prefs import Channel
from scanner.signals.broker_adjust import adjust

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


def dispatch_watch(
    conn: db.Conn,
    tickers: Sequence[str],
    session: str,
    senders: Mapping[Channel, Sender],
    now: datetime,
    base_url: str,
) -> int:
    """One evening digest of stocks that joined the watch list (spec 08, written by stock_eod)."""
    if not tickers:
        return 0
    rows = conn.execute(
        "SELECT ticker, close, high_52w, apr_10 FROM stock_screen_results "
        "WHERE session_date = %s AND ticker = ANY(%s)",
        (session, list(tickers)),
    ).fetchall()
    order = {t: k for k, t in enumerate(tickers)}
    rows.sort(key=lambda r: order[r[0]])
    msg = watch_message(
        [WatchRow(t, float(c), float((h - c) / h), _f(a10)) for t, c, h, a10 in rows],
        session,
        base_url,
    )
    with conn.transaction():
        return sum(
            enqueue(
                conn,
                plan_for(
                    r,
                    kind="digest",
                    message=msg,
                    dedupe_key=f"watch:{session}",
                    now=now,
                    senders=senders,
                    strategy="stocks",
                ),
                now,
            )
            for r in recipients(conn)
        )


def _voted(evidence: dict[str, Any] | None, names: Mapping[str, str]) -> list[str]:
    if not evidence:
        return []
    out = []
    for key, e in evidence.items():
        if not e.get("fired"):
            continue
        label = names.get(key, key)
        if key == "stocks.ind_candle" and e.get("patterns"):
            label = f"{label} ({', '.join(p.replace('_', ' ') for p in e['patterns'])})"
        out.append(label)
    return out


def dispatch_stock_events(
    conn: db.Conn,
    event_ids: Sequence[int],
    senders: Mapping[Channel, Sender],
    now: datetime,
    base_url: str,
) -> int:
    """Buys, sells, and updates on stock buys (spec 08 alerts), to everyone with stock alerts on.
    Buys and sells are "signal" notifications; the rest are updates."""
    if not event_ids:
        return 0
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT e.signal_id, e.kind, e.session, e.price, s.ticker, s.buy_session, s.entry, "
            "s.stop_initial, s.projection, s.projection_pct, s.horizon_sessions, s.votes, "
            "s.exit_votes, s.has_provisional, s.highest_close, s.stop_now "
            "FROM stock_signal_events e "
            "JOIN stock_signals s ON s.id = e.signal_id WHERE e.id = ANY(%s) ORDER BY e.id",
            (list(event_ids),),
        )
        events = cur.fetchall()
    stop_pct = float(_param(conn, "stocks.stop_loss", "stop_pct") or 5)
    written = 0
    with conn.transaction():
        people = recipients(conn)
        for e in events:
            kind = str(e["kind"])
            entry = float(e["entry"])
            price = float(e["price"])
            msg: Message
            if kind == "bought":
                msg = stock_buy_message(
                    StockBuy(
                        str(e["signal_id"]), e["ticker"], str(e["session"]), entry,
                        float(e["stop_initial"]), stop_pct, float(e["projection"]),
                        float(e["projection_pct"]), int(e["horizon_sessions"]),
                        _voted(e["votes"], INDICATOR_NAMES), bool(e["has_provisional"]),
                    ),
                    base_url,
                )  # fmt: skip
                note = "signal"
            elif kind in ("stopped", "trailing_stopped", "sold"):
                sessions = _sessions_between(conn, e["ticker"], e["buy_session"], e["session"])
                msg = stock_exit_message(
                    ticker=e["ticker"], kind=kind, price=price, entry=entry, sessions=sessions,
                    highest=float(e["highest_close"]), voted=_voted(e["exit_votes"], SELL_NAMES),
                    base_url=base_url,
                )  # fmt: skip
                note = "signal"
            else:
                msg = stock_update_message(
                    ticker=e["ticker"], kind=kind, price=price, entry=entry,
                    stop=_f(e["stop_now"]), projection=float(e["projection"]),
                    horizon=int(e["horizon_sessions"]), base_url=base_url,
                )  # fmt: skip
                note = "update"
            for r in people:
                written += enqueue(
                    conn,
                    plan_for(
                        r,
                        kind="signal" if note == "signal" else "update",
                        message=msg,
                        dedupe_key=f"stock:{e['signal_id']}:{kind}",
                        now=now,
                        senders=senders,
                        strategy="stocks",
                    ),
                    now,
                )
    return written


def _param(conn: db.Conn, key: str, name: str) -> str | None:
    row = conn.execute(
        "SELECT v.params ->> %s FROM rule_definitions d JOIN rule_versions v "
        "ON v.key = d.key AND v.version = d.current_version WHERE d.key = %s",
        (name, key),
    ).fetchone()
    return str(row[0]) if row and row[0] is not None else None


def _sessions_between(conn: db.Conn, ticker: str, first: date, last: date) -> int:
    row = conn.execute(
        "SELECT count(*) FROM stock_daily_bars WHERE ticker = %s AND session_date > %s "
        "AND session_date <= %s",
        (ticker, first, last),
    ).fetchone()
    return int(row[0]) if row else 0


def dispatch_holdings(
    conn: db.Conn,
    alerts: Sequence[dict[str, Any]],
    session: str,
    senders: Mapping[Channel, Sender],
    now: datetime,
    base_url: str,
) -> int:
    """Holding alerts (stops, sell signal, projection) go to the holding's owner only."""
    written = 0
    with conn.transaction():
        for a in alerts:
            row = conn.execute(
                "SELECT user_id, ticker, purchase_price, purchase_date, expected_profit_pct, "
                "horizon_sessions, highest_close, stop_now FROM holdings WHERE id = %s",
                (a["holding_id"],),
            ).fetchone()
            if row is None:
                continue
            user_id, ticker, price, bought, pct, horizon, highest, stop_now = row
            entry = float(price)
            close = float(a["price"])
            projection = entry * (1 + float(pct) / 100)
            if a["alert"] in ("stopped", "trailing_stopped", "sold"):
                msg = stock_exit_message(
                    ticker=ticker, kind=a["alert"], price=close, entry=entry,
                    sessions=_sessions_between(conn, ticker, bought, date.fromisoformat(session)),
                    highest=float(highest or price), voted=[], base_url=base_url, holding=True,
                )  # fmt: skip
            else:
                msg = stock_update_message(
                    ticker=ticker, kind=a["alert"], price=close, entry=entry, stop=_f(stop_now),
                    projection=projection, horizon=int(horizon), base_url=base_url, holding=True,
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
