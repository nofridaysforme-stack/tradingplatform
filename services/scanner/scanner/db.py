"""Connection pool and repositories. All SQL the scanner runs lives here."""

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from scanner.data.base import Candle, DailyBar, TickerRef
from scanner.instruments import Instrument

# The newest migration in db/migrations. A test keeps this in step with the folder.
EXPECTED_SCHEMA_VERSION = "20261003000001"

Conn = psycopg.Connection[Any]


class SchemaBehindError(RuntimeError):
    pass


def make_pool(database_url: str, *, max_size: int = 4) -> ConnectionPool:
    return ConnectionPool(database_url, min_size=1, max_size=max_size, open=True)


def check_schema(conn: Conn, expected: str = EXPECTED_SCHEMA_VERSION) -> str:
    """Raise unless the database has at least the expected migration applied."""
    try:
        row = conn.execute("SELECT max(version) FROM schema_migrations").fetchone()
    except psycopg.errors.UndefinedTable as exc:
        conn.rollback()
        raise SchemaBehindError("schema_migrations missing; run db/migrate.sh") from exc
    current = row[0] if row and row[0] else ""
    if current < expected:
        raise SchemaBehindError(
            f"database schema is at {current or 'nothing'}, scanner expects {expected}"
        )
    return str(current)


# Instruments and calendar


def list_instruments(conn: Conn, *, enabled_only: bool = True) -> list[Instrument]:
    sql = (
        "SELECT id, symbol, provider_code, pip_size, display_decimals, enabled "
        "FROM instruments WHERE asset_class = 'forex'"
    )
    if enabled_only:
        sql += " AND enabled"
    sql += " ORDER BY sort_order, symbol"
    with conn.cursor(row_factory=dict_row) as cur:
        return [Instrument(**row) for row in cur.execute(sql)]


def get_instrument(conn: Conn, symbol: str) -> Instrument:
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            "SELECT id, symbol, provider_code, pip_size, display_decimals, enabled "
            "FROM instruments WHERE symbol = %s",
            (symbol,),
        ).fetchone()
    if row is None:
        raise LookupError(f"unknown instrument {symbol}")
    return Instrument(**row)


def holidays(conn: Conn, market: str) -> set[date]:
    rows = conn.execute("SELECT day FROM market_holidays WHERE market = %s", (market,))
    return {r[0] for r in rows}


# Rules (minimal read path; the full registry arrives with the rules engine)


def rule_params(conn: Conn, key: str, instrument_id: UUID | None = None) -> dict[str, Any]:
    """Resolution order (spec 05): instrument override, then the version's value, then default."""
    row = conn.execute(
        "SELECT v.params_schema, v.params FROM rule_definitions d "
        "JOIN rule_versions v ON v.key = d.key AND v.version = d.current_version "
        "WHERE d.key = %s",
        (key,),
    ).fetchone()
    if row is None:
        raise LookupError(f"unknown rule {key}")
    schema: dict[str, Any] = row[0]
    params: dict[str, Any] = {name: spec.get("default") for name, spec in schema.items()}
    params.update(row[1])
    if instrument_id is not None:
        override = conn.execute(
            "SELECT params FROM strategy_param_overrides WHERE key = %s AND instrument_id = %s",
            (key, instrument_id),
        ).fetchone()
        if override is not None:
            params.update(override[0])
    return params


# Forex candles and levels


def upsert_candles(conn: Conn, instrument_id: UUID, candles: Iterable[Candle]) -> int:
    """Stores completed candles only. Returns the number written."""
    rows = [
        (instrument_id, c.granularity, c.ts, c.o, c.h, c.l, c.c, c.volume)
        for c in candles
        if c.complete
    ]
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO candles (instrument_id, granularity, ts, o, h, l, c, volume) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (instrument_id, granularity, ts) DO UPDATE SET "
            "o = EXCLUDED.o, h = EXCLUDED.h, l = EXCLUDED.l, c = EXCLUDED.c, "
            "volume = EXCLUDED.volume",
            rows,
        )
    return len(rows)


def latest_candle_ts(conn: Conn, instrument_id: UUID, granularity: str) -> datetime | None:
    row = conn.execute(
        "SELECT max(ts) FROM candles WHERE instrument_id = %s AND granularity = %s",
        (instrument_id, granularity),
    ).fetchone()
    return row[0] if row else None


def candle_at(conn: Conn, instrument_id: UUID, granularity: str, ts: datetime) -> Candle | None:
    return _one_candle(
        conn,
        "WHERE instrument_id = %s AND granularity = %s AND ts = %s",
        (instrument_id, granularity, ts),
    )


def last_candle_before(
    conn: Conn, instrument_id: UUID, granularity: str, before: datetime
) -> Candle | None:
    return _one_candle(
        conn,
        "WHERE instrument_id = %s AND granularity = %s AND ts < %s ORDER BY ts DESC LIMIT 1",
        (instrument_id, granularity, before),
    )


def _one_candle(conn: Conn, where: str, args: tuple[Any, ...]) -> Candle | None:
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(
            "SELECT i.provider_code AS instrument, granularity, ts, o, h, l, c, volume "
            f"FROM candles JOIN instruments i ON i.id = candles.instrument_id {where}",
            args,
        ).fetchone()
    return Candle(**row, complete=True) if row else None


def upsert_levels(
    conn: Conn, instrument_id: UUID, trading_day: date, set_kind: str, data: dict[str, Any]
) -> None:
    conn.execute(
        "INSERT INTO levels (instrument_id, trading_day, set_kind, data) "
        "VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (instrument_id, trading_day, set_kind) DO UPDATE SET "
        "data = EXCLUDED.data, computed_at = now()",
        (instrument_id, trading_day, set_kind, Jsonb(data)),
    )


def get_levels(conn: Conn, instrument_id: UUID, trading_day: date) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT set_kind, data FROM levels WHERE instrument_id = %s AND trading_day = %s",
        (instrument_id, trading_day),
    )
    return {str(r[0]): r[1] for r in rows}


# Stocks


def upsert_stock_bars(conn: Conn, bars: Iterable[DailyBar]) -> int:
    rows = [(b.ticker, b.session_date, b.o, b.h, b.l, b.c, b.volume) for b in bars]
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO stock_daily_bars (ticker, session_date, o, h, l, c, volume) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (ticker, session_date) DO UPDATE SET "
            "o = EXCLUDED.o, h = EXCLUDED.h, l = EXCLUDED.l, c = EXCLUDED.c, "
            "volume = EXCLUDED.volume",
            rows,
        )
    return len(rows)


def replace_ticker_history(conn: Conn, ticker: str, bars: list[DailyBar]) -> int:
    """After a split, a ticker's stored bars are replaced by freshly adjusted history."""
    with conn.transaction():
        conn.execute("DELETE FROM stock_daily_bars WHERE ticker = %s", (ticker,))
        return upsert_stock_bars(conn, bars)


def stock_sessions_present(conn: Conn, sessions: Iterable[date]) -> set[date]:
    rows = conn.execute(
        "SELECT DISTINCT session_date FROM stock_daily_bars WHERE session_date = ANY(%s)",
        (list(sessions),),
    )
    return {r[0] for r in rows}


def earliest_stock_session(conn: Conn) -> date | None:
    row = conn.execute("SELECT min(session_date) FROM stock_daily_bars").fetchone()
    return row[0] if row else None


def sync_tickers(conn: Conn, refs: Iterable[TickerRef]) -> tuple[int, int]:
    """Upsert the active list; mark tickers missing from it inactive. Returns (active, retired)."""
    rows = [(r.ticker, r.name, r.exchange) for r in refs]
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO stock_tickers (ticker, name, exchange, active, updated_at) "
            "VALUES (%s, %s, %s, true, now()) "
            "ON CONFLICT (ticker) DO UPDATE SET name = EXCLUDED.name, "
            "exchange = EXCLUDED.exchange, active = true, updated_at = now()",
            rows,
        )
        cur.execute(
            "UPDATE stock_tickers SET active = false, updated_at = now() "
            "WHERE active AND NOT (ticker = ANY(%s))",
            ([r[0] for r in rows],),
        )
        retired = cur.rowcount
    return len(rows), retired


# Strategy runs


def recent_candles(
    conn: Conn, instrument_id: UUID, granularity: str, upto: datetime, limit: int
) -> list[tuple[datetime, float, float, float, float]]:
    """The last `limit` completed candles with ts <= upto, oldest first."""
    rows = conn.execute(
        "SELECT ts, o, h, l, c FROM candles WHERE instrument_id = %s AND granularity = %s "
        "AND ts <= %s ORDER BY ts DESC LIMIT %s",
        (instrument_id, granularity, upto, limit),
    ).fetchall()
    return [(r[0], float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in reversed(rows)]


def strategy_configs(conn: Conn) -> dict[str, tuple[bool, list[UUID] | None]]:
    rows = conn.execute("SELECT strategy::text, enabled, instrument_ids FROM strategy_configs")
    return {r[0]: (bool(r[1]), r[2]) for r in rows}


Impact = Literal["high", "medium", "low"]


def econ_events(conn: Conn, since: datetime, until: datetime) -> list[tuple[datetime, str, Impact]]:
    rows = conn.execute(
        "SELECT at, currency, impact::text FROM econ_events WHERE at BETWEEN %s AND %s",
        (since, until),
    )
    return [(r[0], str(r[1]).strip(), cast(Impact, r[2])) for r in rows]


def heartbeat(conn: Conn, version: str, market: dict[str, Any] | None = None) -> None:
    conn.execute(
        "INSERT INTO worker_heartbeat (id, at, version, market) VALUES (true, now(), %s, %s) "
        "ON CONFLICT (id) DO UPDATE SET at = now(), version = EXCLUDED.version, "
        "market = EXCLUDED.market",
        (version, Jsonb(market) if market is not None else None),
    )


def instruments_without_history(conn: Conn) -> list[Instrument]:
    """Enabled pairs with no daily bars yet: an admin just added them (spec 14 upsertInstrument)."""
    have = {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT instrument_id FROM candles WHERE granularity = 'D'"
        ).fetchall()
    }
    return [i for i in list_instruments(conn) if i.id not in have]


def last_m15_bars(conn: Conn) -> dict[str, datetime | None]:
    """Open time of the newest stored M15 bar for each enabled pair."""
    rows = conn.execute(
        "SELECT i.symbol, (SELECT max(c.ts) FROM candles c WHERE c.instrument_id = i.id "
        "AND c.granularity = 'M15') FROM instruments i WHERE i.enabled ORDER BY i.symbol"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


# Stocks: screener inputs and outputs


def stock_bars_since(
    conn: Conn, since: date, tickers: list[str] | None = None
) -> list[tuple[Any, ...]]:
    """(ticker, session_date, h, l, c, volume) ordered by ticker then date."""
    sql = (
        "SELECT b.ticker, b.session_date, b.h, b.l, b.c, b.volume FROM stock_daily_bars b "
        "JOIN stock_tickers t ON t.ticker = b.ticker AND t.active "
        "WHERE b.session_date >= %s"
    )
    args: list[Any] = [since]
    if tickers is not None:
        sql += " AND b.ticker = ANY(%s)"
        args.append(tickers)
    sql += " ORDER BY b.ticker, b.session_date"
    return list(conn.execute(sql, args).fetchall())


def active_tickers(conn: Conn, exchanges: list[str]) -> list[str]:
    rows = conn.execute(
        "SELECT ticker FROM stock_tickers WHERE active AND exchange = ANY(%s)", (exchanges,)
    )
    return [r[0] for r in rows]


def stock_sessions_before(conn: Conn, session: date, count: int) -> list[date]:
    rows = conn.execute(
        "SELECT DISTINCT session_date FROM stock_daily_bars WHERE session_date < %s "
        "ORDER BY session_date DESC LIMIT %s",
        (session, count),
    )
    return [r[0] for r in rows]


def upsert_screen_results(conn: Conn, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    cols = list(rows[0])
    placeholders = ", ".join(["%s"] * len(cols))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in ("session_date", "ticker"))
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO stock_screen_results ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT (session_date, ticker) DO UPDATE SET {updates}",
            [[Jsonb(r[c]) if c == "version_set" else r[c] for c in cols] for r in rows],
        )
    return len(rows)


def confirmed_between(conn: Conn, first: date, last: date) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM stock_screen_results WHERE status = 'trend_confirmed' "
        "AND session_date BETWEEN %s AND %s",
        (first, last),
    )
    return {r[0] for r in rows}


def open_holdings(conn: Conn) -> list[tuple[Any, ...]]:
    """(id, user_id, ticker, purchase_price, purchase_date, expected_profit_pct, horizon)."""
    return list(
        conn.execute(
            "SELECT id, user_id, ticker, purchase_price, purchase_date, expected_profit_pct, "
            "horizon_sessions FROM holdings WHERE NOT closed"
        ).fetchall()
    )


# Retention (spec 09)

RETENTION_SQL = (
    (
        "candles_m15",
        "DELETE FROM candles WHERE granularity = 'M15' AND ts < now() - interval '2 years'",
    ),
    (
        "stock_screen_results",
        "DELETE FROM stock_screen_results WHERE session_date < current_date - interval '2 years'",
    ),
    ("notifications", "DELETE FROM notifications WHERE created_at < now() - interval '180 days'"),
    ("job_runs", "DELETE FROM job_runs WHERE started_at < now() - interval '90 days'"),
    (
        "stock_daily_bars",
        "DELETE FROM stock_daily_bars WHERE session_date < ("
        "SELECT min(d) FROM (SELECT DISTINCT session_date AS d FROM stock_daily_bars "
        "ORDER BY d DESC LIMIT 400) recent)",
    ),
)


def apply_retention(conn: Conn) -> dict[str, int]:
    deleted: dict[str, int] = {}
    for name, sql in RETENTION_SQL:
        cur = conn.execute(sql)
        deleted[name] = cur.rowcount
    return deleted


# Job runs


def start_job(conn: Conn, job: str, detail: dict[str, Any] | None = None) -> int:
    row = conn.execute(
        "INSERT INTO job_runs (job, detail) VALUES (%s, %s) RETURNING id",
        (job, Jsonb(detail or {})),
    ).fetchone()
    assert row is not None
    return int(row[0])


def update_job(conn: Conn, run_id: int, detail: dict[str, Any]) -> None:
    conn.execute("UPDATE job_runs SET detail = %s WHERE id = %s", (Jsonb(detail), run_id))


def finish_job(conn: Conn, run_id: int, ok: bool, detail: dict[str, Any]) -> None:
    conn.execute(
        "UPDATE job_runs SET finished_at = now(), ok = %s, detail = %s WHERE id = %s",
        (ok, Jsonb(detail), run_id),
    )


def decimal_json(value: Decimal) -> float:
    """Levels are stored as JSON numbers rounded to 8 decimal places (the price precision)."""
    return float(value.quantize(Decimal("0.00000001")))
