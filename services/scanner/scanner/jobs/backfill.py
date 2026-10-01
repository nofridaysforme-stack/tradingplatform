"""One-off backfills (spec 04).

    python -m scanner.jobs.backfill forex [--instrument EUR/USD]
    python -m scanner.jobs.backfill stocks [--sessions 300]

Forex: M15 for 120 trading days, D for 400 days, W for 104 weeks, M for 36 months, then
levels for the most recent trading days. Stocks: grouped daily bars for the last 300
sessions at 5 calls per minute (about an hour), skipping sessions already stored, then
the ticker universe. Progress is written to job_runs.
"""

import argparse
import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from scanner import db
from scanner.config import MASSIVE_HOST, Settings
from scanner.data.base import ProviderError, StockDataProvider
from scanner.data.massive import MassiveClient
from scanner.data.oanda import OandaClient
from scanner.data.sync import load_grouped_day, now_utc, refresh_universe, sync_forex
from scanner.instruments import Instrument
from scanner.levels.compute import compute_and_store
from scanner.main import configure_logging
from scanner.time import (
    forex_trading_days_back,
    trading_day_of,
    trading_day_start,
    us_stock_sessions_back,
)

log = logging.getLogger(__name__)

M15_TRADING_DAYS = 120
D_DAYS = 400
W_WEEKS = 104
M_MONTHS = 36
STOCK_SESSIONS = 300
LEVEL_DAYS = 5


def _months_back(ts: datetime, months: int) -> datetime:
    y, m = divmod(ts.year * 12 + ts.month - 1 - months, 12)
    return ts.replace(year=y, month=m + 1, day=1)


def forex_starts(now: datetime, holidays: set[date]) -> dict[str, datetime]:
    today = trading_day_of(now)
    return {
        "M15": trading_day_start(forex_trading_days_back(today, M15_TRADING_DAYS, holidays)),
        "D": now - timedelta(days=D_DAYS),
        "W": now - timedelta(weeks=W_WEEKS),
        "M": _months_back(now, M_MONTHS),
    }


def backfill_forex(
    conn: db.Conn,
    client: OandaClient,
    instruments: list[Instrument],
    now: datetime,
) -> dict[str, Any]:
    hol = db.holidays(conn, "forex")
    starts = forex_starts(now, hol)
    run_id = db.start_job(conn, "backfill", {"kind": "forex"})
    detail: dict[str, Any] = {"kind": "forex", "instruments": {}}
    ok = True
    try:
        for inst in instruments:
            counts = {g: sync_forex(conn, client, inst, g, start) for g, start in starts.items()}
            day = trading_day_of(now)
            levels_for = [forex_trading_days_back(day, i, hol) for i in range(LEVEL_DAYS)]
            for d in levels_for:
                compute_and_store(conn, inst, d, hol)
            detail["instruments"][inst.symbol] = {
                "candles": counts,
                "levels_days": [d.isoformat() for d in levels_for],
            }
            db.update_job(conn, run_id, detail)
    except ProviderError as exc:
        ok = False
        detail["error"] = str(exc)
        raise
    finally:
        db.finish_job(conn, run_id, ok, detail)
    return detail


def backfill_stocks(
    conn: db.Conn,
    provider: StockDataProvider,
    today: date,
    sessions: int = STOCK_SESSIONS,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    hol = db.holidays(conn, "us_stocks")
    # Today's session is not published until the evening, so start from yesterday.
    wanted = us_stock_sessions_back(today - timedelta(days=1), sessions, hol)
    have = db.stock_sessions_present(conn, wanted)
    todo = [d for d in wanted if d not in have]
    run_id = db.start_job(conn, "backfill", {"kind": "stocks", "todo": len(todo)})
    detail: dict[str, Any] = {
        "kind": "stocks",
        "wanted": len(wanted),
        "already_stored": len(have),
        "loaded": 0,
        "empty_sessions": [],
    }
    ok = True
    try:
        for i, session in enumerate(todo, start=1):
            if load_grouped_day(conn, provider, session) == 0:
                detail["empty_sessions"].append(session.isoformat())
            else:
                detail["loaded"] += 1
            if i % 10 == 0 or i == len(todo):
                db.update_job(conn, run_id, {**detail, "progress": f"{i}/{len(todo)}"})
                if on_progress:
                    on_progress(i, len(todo))
        active, retired = refresh_universe(conn, provider)
        detail["tickers"] = {"active": active, "retired": retired}
    except ProviderError as exc:
        ok = False
        detail["error"] = str(exc)
        raise
    finally:
        db.finish_job(conn, run_id, ok, detail)
    return detail


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m scanner.jobs.backfill")
    sub = parser.add_subparsers(dest="kind", required=True)
    fx = sub.add_parser("forex")
    fx.add_argument("--instrument", help="one symbol, e.g. EUR/USD (default: all enabled)")
    st = sub.add_parser("stocks")
    st.add_argument("--sessions", type=int, default=STOCK_SESSIONS)
    args = parser.parse_args(argv)

    configure_logging()
    settings = Settings()  # values come from the environment
    with db.make_pool(settings.database_url, max_size=1) as pool, pool.connection() as conn:
        conn.autocommit = True
        db.check_schema(conn)
        if args.kind == "forex":
            if settings.oanda_api_token is None:
                raise SystemExit("OANDA_API_TOKEN is not set")
            client = OandaClient(settings.oanda_api_token.get_secret_value(), settings.oanda_host)
            instruments = (
                [db.get_instrument(conn, args.instrument)]
                if args.instrument
                else db.list_instruments(conn)
            )
            backfill_forex(conn, client, instruments, now_utc())
        else:
            if settings.massive_api_key is None:
                raise SystemExit("MASSIVE_API_KEY is not set")
            provider = MassiveClient(settings.massive_api_key.get_secret_value(), MASSIVE_HOST)
            backfill_stocks(
                conn,
                provider,
                now_utc().date(),
                args.sessions,
                on_progress=lambda i, n: log.info("stock backfill %s/%s", i, n),
            )


if __name__ == "__main__":
    main()
