"""stock_eod (spec 03): 18:30 New York on US trading days, retried every 15 minutes until
23:00. Load the session's grouped bars, refetch split tickers, run the screener, and find
digest candidates and holdings that need an alert (sent from Phase 6).

    python -m scanner.jobs.stock_eod --date YYYY-MM-DD
"""

import argparse
import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from scanner import db
from scanner.config import MASSIVE_HOST, Settings
from scanner.data.base import StockDataProvider
from scanner.data.massive import MassiveClient
from scanner.data.sync import load_grouped_day, refetch_split_tickers
from scanner.main import configure_logging
from scanner.rules.registry import Registry, RuleSet
from scanner.strategies import stock_momentum as sm
from scanner.strategies.stock_screener import DayBar, ScreenResult, screen

log = logging.getLogger(__name__)
# Calendar days of bars to load: covers 300 sessions with holidays.
HISTORY_DAYS = 450


def run(
    conn: db.Conn, provider: StockDataProvider, registry: Registry, session: date
) -> dict[str, Any]:
    """Returns {"ready": False} when Massive has not published the session yet."""
    if session in db.holidays(conn, "us_stocks") or session.weekday() >= 5:
        return {"ready": True, "skipped": "not a session"}
    loaded = load_grouped_day(conn, provider, session)
    if loaded == 0:
        return {"ready": False, "session": session.isoformat()}
    split = refetch_split_tickers(conn, provider, session)
    registry.refresh(conn)
    detail = screen_session(conn, registry.ruleset, session)
    return {
        "ready": True,
        "session": session.isoformat(),
        "bars": loaded,
        "splits": split,
        **detail,
    }


def screen_session(conn: db.Conn, rules: RuleSet, session: date) -> dict[str, Any]:
    """The spec 08 funnel for one session: screen every stock, then the watch list, buys,
    open buys, and open holdings."""
    exchanges = list(rules.params("stocks.universe")["exchanges"])
    universe = set(db.active_tickers(conn, exchanges))
    since = date.fromordinal(session.toordinal() - HISTORY_DAYS)
    by_ticker: dict[str, list[DayBar]] = defaultdict(list)
    for ticker, d, h, low, c, v, o in db.stock_bars_since(conn, since):
        if ticker in universe and d <= session:
            by_ticker[ticker].append(
                DayBar(d, Decimal(h), Decimal(low), Decimal(c), int(v), Decimal(o))
            )

    version_set = rules.version_set(strategy="stocks")
    results: dict[str, ScreenResult] = {}
    for ticker, bars in by_ticker.items():
        if bars[-1].session_date != session:
            continue
        r = screen(ticker, bars, rules)
        if r is not None:
            results[ticker] = r

    fired_cache: dict[str, dict[str, sm.Fired]] = {}

    def fired_for(ticker: str) -> dict[str, sm.Fired]:
        if ticker not in fired_cache:
            fired_cache[ticker] = sm.indicators(by_ticker[ticker], rules)
        return fired_cache[ticker]

    open_signals = {s["ticker"]: s for s in db.open_stock_signals(conn)}
    last_exits = db.last_stock_exits(conn)
    watch_sessions = int(rules.params("stocks.watch")["watch_sessions"])

    rows: list[dict[str, Any]] = []
    joined: list[str] = []
    buys: list[dict[str, Any]] = []
    for ticker, r in results.items():
        bars = by_ticker[ticker]
        today = len(bars) - 1
        fired = fired_for(ticker)
        if ticker in open_signals:
            day = sm.Day(today, r, sm.passes_momentum(bars, rules), False, False)
        else:
            exit_session = last_exits.get(ticker)
            state = sm.WatchState(
                blocked_through=sm.last_index_on_or_before(bars, exit_session)
                if exit_session
                else -1
            )
            for i in range(max(0, today - watch_sessions), today + 1):
                day = sm.step(ticker, bars, i, rules, state)
        row = r.as_row(version_set)
        row.update(
            momentum=day.momentum,
            watching=day.watching,
            indicators=sm.today_values(bars, fired, rules),
        )
        rows.append(row)
        if day.joined:
            joined.append(ticker)
        if sm.is_buy(bars, fired, day, rules):
            buys.append(_buy_row(ticker, bars, fired, today, rules))
    with conn.transaction():
        db.upsert_screen_results(conn, rows)

    new_events: list[int] = []
    with conn.transaction():
        for b in buys:
            sid = db.insert_stock_signal(conn, b)
            if sid is not None:
                event = db.add_stock_event(conn, sid, session, "bought", b["entry"])
                new_events += [event] if event is not None else []
        for sig in open_signals.values():
            if sig["ticker"] in by_ticker and by_ticker[sig["ticker"]][-1].session_date == session:
                new_events += _follow_signal(conn, sig, by_ticker[sig["ticker"]], fired_for, rules)

    holdings = _follow_holdings(conn, by_ticker, fired_for, rules, session)
    max_digest = int(rules.params("stocks.alert_watch")["max_in_digest"])
    joined.sort(key=lambda t: results[t].five.apr.get(10, Decimal(0)), reverse=True)
    return {
        "screened": len(by_ticker),
        "qualified": len(results),
        "momentum": sum(1 for row in rows if row["momentum"]),
        "watching": sum(1 for row in rows if row["watching"]),
        "buys": len(buys),
        "watch_digest": joined[:max_digest] if rules.enabled("stocks.alert_watch") else [],
        "stock_events": new_events,
        "holdings": holdings,
    }


def _buy_row(
    ticker: str, bars: list[DayBar], fired: dict[str, sm.Fired], i: int, rules: RuleSet
) -> dict[str, Any]:
    """A buy on session i, with the evidence it stores (CLAUDE.md rule 3)."""
    entry = bars[i].c
    p = sm.plan(entry, rules)
    window = sm.window_of("stocks.buy_vote", rules)
    found = sm.buy_votes(bars, fired, i, rules)
    stop = p.stop_initial if p.stop_initial is not None else Decimal(0)
    keys = ["stocks.momentum", "stocks.watch", "stocks.buy_vote", "stocks.projection",
            "stocks.stop_loss", "stocks.trailing_stop", "stocks.sell_vote",
            "stocks.rule1_near_high", "stocks.rule2_double", "stocks.rule3_apr",
            *sm.INDICATORS]  # fmt: skip
    return {
        "ticker": ticker,
        "buy_session": bars[i].session_date,
        "entry": entry,
        "stop_initial": _q(stop),
        "projection": _q(p.projection),
        "projection_pct": p.projection_pct,
        "horizon_sessions": p.horizon_sessions,
        "highest_close": entry,
        "stop_now": _q(stop),
        "last_session": bars[i].session_date,
        "votes": sm.evidence(bars, fired, i, "buy", window, rules),
        "version_set": rules.version_set([k for k in keys if rules.has(k)]),
        "has_provisional": sm.has_provisional(found, rules),
    }


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.000001"))


def _track_fields(t: sm.Track) -> dict[str, Any]:
    """Where a buy or a holding stands, in the shape both tables share."""
    return {
        "highest_close": t.highest_close,
        "trailing_active": t.trailing_active,
        "stop_now": _q(t.stop_now) if t.stop_now is not None else None,
    }


def _follow_signal(
    conn: db.Conn,
    sig: dict[str, Any],
    bars: list[DayBar],
    fired_for: Callable[[str], dict[str, sm.Fired]],
    rules: RuleSet,
) -> list[int]:
    """Replays an open buy from its entry to today and records what changed. Returns the ids
    of events written today, for the alerts."""
    entry_index = sm.session_index(bars, sig["buy_session"])
    if entry_index is None:
        log.warning("buy older than the loaded history", extra={"ticker": sig["ticker"]})
        return []
    entry = Decimal(sig["entry"])
    plan = sm.Plan(
        entry,
        Decimal(sig["stop_initial"]),
        Decimal(sig["projection"]),
        Decimal(sig["projection_pct"]),
        int(sig["horizon_sessions"]),
        Decimal(0),
        Decimal(0),
    )
    t = sm.track(bars, fired_for(sig["ticker"]), entry_index, plan, rules)
    fields = _track_fields(t)
    fields["stop_now"] = fields["stop_now"] if fields["stop_now"] is not None else sig["stop_now"]
    fields["last_session"] = bars[t.last_index].session_date
    if t.projection_index is not None:
        fields["projection_session"] = bars[t.projection_index].session_date
    if t.exit is not None:
        fields.update(
            state=t.exit.kind,
            exit_session=bars[t.exit.index].session_date,
            exit_price=t.exit.price,
            result_pct=_q(sm.result_pct(entry, t.exit.price)),
            exit_votes=sm.evidence(
                bars, fired_for(sig["ticker"]), t.exit.index, "sell",
                sm.window_of("stocks.sell_vote", rules), rules, after=entry_index,
            ) if t.exit.kind == "sold" else None,
        )  # fmt: skip
    db.update_stock_signal(conn, sig["id"], fields)
    written: list[int] = []
    today = len(bars) - 1
    for e in t.events:
        event_id = db.add_stock_event(
            conn, sig["id"], bars[e.index].session_date, e.kind, e.price, e.detail
        )
        if event_id is not None and e.index == today:
            written.append(event_id)
    return written


HOLDING_ALERTS = {
    "stopped": None,
    "trailing_stopped": None,
    "sold": None,
    "projection_reached": "stocks.alert_projection",
    "horizon_passed": "stocks.alert_horizon",
}


def _follow_holdings(
    conn: db.Conn,
    by_ticker: dict[str, list[DayBar]],
    fired_for: Callable[[str], dict[str, sm.Fired]],
    rules: RuleSet,
    session: date,
) -> list[dict[str, Any]]:
    """The same stops and sell vote on each open holding, from the owner's purchase price and
    date. Writes where the holding stands; returns today's alerts for its owner."""
    out: list[dict[str, Any]] = []
    for hid, _user, ticker, price, bought, pct, horizon in db.open_holdings(conn):
        bars = by_ticker.get(ticker)
        if not bars or bars[-1].session_date != session:
            continue
        entry_index = sm.last_index_on_or_before(bars, bought)
        if entry_index < 0:
            continue
        entry = Decimal(price)
        plan = sm.plan(entry, rules, Decimal(pct), int(horizon))
        t = sm.track(bars, fired_for(ticker), entry_index, plan, rules)
        fields = _track_fields(t)
        fields["tracked_session"] = session
        if t.exit is not None:
            fields.update(
                sell_reason=t.exit.kind,
                sell_session=bars[t.exit.index].session_date,
                sell_price=t.exit.price,
            )
        db.update_holding_track(conn, hid, fields)
        today = len(bars) - 1
        for e in t.events:
            rule = HOLDING_ALERTS.get(e.kind, "skip")
            if e.index != today or rule == "skip" or (rule is not None and not rules.enabled(rule)):
                continue
            out.append({"holding_id": str(hid), "ticker": ticker, "alert": e.kind,
                        "price": str(e.price)})  # fmt: skip
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m scanner.jobs.stock_eod")
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    args = parser.parse_args(argv)
    configure_logging()
    settings = Settings()  # values come from the environment
    if settings.massive_api_key is None:
        raise SystemExit("MASSIVE_API_KEY is not set")
    with db.make_pool(settings.database_url, max_size=1) as pool, pool.connection() as conn:
        conn.autocommit = True
        db.check_schema(conn)
        provider = MassiveClient(settings.massive_api_key.get_secret_value(), MASSIVE_HOST)
        run_id = db.start_job(conn, "stock_eod", {"session": args.date.isoformat(), "manual": True})
        detail = run(conn, provider, Registry.load(conn), args.date)
        db.finish_job(conn, run_id, bool(detail.get("ready")), detail)
        log.info("stock_eod finished", extra=detail)


if __name__ == "__main__":
    main()
