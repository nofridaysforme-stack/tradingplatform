"""Pull provider data into Postgres. Shared by backfill and the scheduled jobs."""

import logging
from datetime import UTC, date, datetime, timedelta

from scanner import db
from scanner.data.base import StockDataProvider, completed
from scanner.data.oanda import OandaClient
from scanner.instruments import Instrument

log = logging.getLogger(__name__)

# History stored per split ticker: enough for the 300-session window with room to spare.
SPLIT_REFETCH_DAYS = 600


def sync_forex(
    conn: db.Conn,
    client: OandaClient,
    instrument: Instrument,
    granularity: str,
    start: datetime,
    end: datetime | None = None,
) -> int:
    """Fetch [start, end) and store the completed candles."""
    candles = client.history(instrument.provider_code, granularity, start, end)
    with conn.transaction():
        written = db.upsert_candles(conn, instrument.id, completed(candles))
    log.info(
        "forex candles stored",
        extra={"instrument": instrument.symbol, "granularity": granularity, "count": written},
    )
    return written


def kept_tickers(conn: db.Conn) -> set[str] | None:
    """The tickers whose daily bars are stored: the stock universe (active common stocks on the
    stocks.universe exchanges) plus any stock an owner still holds. Massive's grouped file also
    carries ETFs, warrants, and funds, about half the rows, which nothing reads. None while the
    ticker list has not been loaded yet, so a first run stores everything rather than nothing."""
    exchanges = list(db.rule_params(conn, "stocks.universe")["exchanges"])
    universe = set(db.active_tickers(conn, exchanges))
    if not universe:
        return None
    return universe | db.held_tickers(conn)


def load_grouped_day(conn: db.Conn, provider: StockDataProvider, session_date: date) -> int:
    """Store one session's grouped bars for the kept tickers. Returns 0 when Massive has not
    published the session yet."""
    bars = provider.grouped_daily(session_date)
    keep = kept_tickers(conn)
    if keep is not None:
        bars = [b for b in bars if b.ticker in keep]
    with conn.transaction():
        return db.upsert_stock_bars(conn, bars)


def refetch_split_tickers(
    conn: db.Conn, provider: StockDataProvider, session_date: date
) -> list[str]:
    """Stored bars are adjusted as of the day they were fetched. When a split executes,
    replace each affected ticker's history with freshly adjusted bars (spec 04)."""
    splits = provider.splits_on(session_date)
    keep = kept_tickers(conn)
    tickers = sorted({s.ticker for s in splits if keep is None or s.ticker in keep})
    start = session_date - timedelta(days=SPLIT_REFETCH_DAYS)
    for ticker in tickers:
        bars = provider.ticker_history(ticker, start, session_date)
        db.replace_ticker_history(conn, ticker, bars)
        log.info("split refetch", extra={"ticker": ticker, "bars": len(bars)})
    return tickers


def refresh_universe(conn: db.Conn, provider: StockDataProvider) -> tuple[int, int]:
    refs = provider.active_common_stocks()
    return db.sync_tickers(conn, refs)


def now_utc() -> datetime:
    return datetime.now(UTC)
