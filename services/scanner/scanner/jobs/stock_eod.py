"""stock_eod (spec 03): 18:30 New York on US trading days, retried every 15 minutes until
23:00. Load the session's grouped bars, refetch split tickers, run the screener, and find
digest candidates and holdings that need an alert (sent from Phase 6).

    python -m scanner.jobs.stock_eod --date YYYY-MM-DD
"""

import argparse
import logging
from collections import defaultdict
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
from scanner.strategies.stock_screener import DayBar, check_holding, digest_candidates, screen

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
    exchanges = list(rules.params("stocks.universe")["exchanges"])
    universe = set(db.active_tickers(conn, exchanges))
    since = date.fromordinal(session.toordinal() - HISTORY_DAYS)
    by_ticker: dict[str, list[DayBar]] = defaultdict(list)
    for ticker, d, h, low, c, v in db.stock_bars_since(conn, since):
        if ticker in universe and d <= session:
            by_ticker[ticker].append(DayBar(d, Decimal(h), Decimal(low), Decimal(c), int(v)))

    version_set = rules.version_set(strategy="stocks")
    results = []
    for ticker, bars in by_ticker.items():
        if bars[-1].session_date != session:
            continue
        r = screen(ticker, bars, rules)
        if r is not None:
            results.append(r)
    with conn.transaction():
        db.upsert_screen_results(conn, [r.as_row(version_set) for r in results])

    cooldown = int(rules.params("stocks.alert_new_confirmed")["cooldown_sessions"])
    prior = db.stock_sessions_before(conn, session, cooldown)
    recent = db.confirmed_between(conn, min(prior), max(prior)) if prior else set()
    digest = (
        digest_candidates(results, recent, rules)
        if rules.enabled("stocks.alert_new_confirmed")
        else []
    )

    holdings = _check_holdings(conn, by_ticker, session)
    return {
        "screened": len(by_ticker),
        "qualified": len(results),
        "confirmed": sum(r.status == "trend_confirmed" for r in results),
        "digest": [r.ticker for r in digest],
        "holdings": holdings,
    }


def _check_holdings(
    conn: db.Conn, by_ticker: dict[str, list[DayBar]], session: date
) -> list[dict[str, Any]]:
    out = []
    for hid, _user, ticker, price, bought, pct, horizon in db.open_holdings(conn):
        bars = by_ticker.get(ticker)
        if not bars or bars[-1].session_date != session:
            continue
        elapsed = sum(1 for b in bars if b.session_date > bought)
        check = check_holding(Decimal(price), Decimal(pct), int(horizon), bars[-1].c, elapsed)
        if check.target_reached or check.time_elapsed:
            out.append({
                "holding_id": str(hid), "ticker": ticker,
                "alert": "target_reached" if check.target_reached else "time_elapsed",
            })  # fmt: skip
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
