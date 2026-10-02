from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb

from scanner import db
from scanner.data.base import Candle, DailyBar, Split, TickerRef
from scanner.data.oanda import parse_candle
from scanner.data.sync import refetch_split_tickers
from scanner.jobs.backfill import backfill_forex, backfill_stocks
from scanner.levels.compute import compute_and_store
from scanner.time import trading_day_start
from tests.conftest import load_fixture

Conn = psycopg.Connection[Any]
MIGRATIONS = Path(__file__).resolve().parents[3] / "db" / "migrations"


def test_expected_schema_version_matches_newest_migration() -> None:
    if not MIGRATIONS.is_dir():
        pytest.skip("db/migrations not present")
    newest = max(p.name.split("_", 1)[0] for p in MIGRATIONS.glob("*.sql"))
    assert newest == db.EXPECTED_SCHEMA_VERSION


def test_check_schema(conn: Conn) -> None:
    assert db.check_schema(conn) >= db.EXPECTED_SCHEMA_VERSION
    with pytest.raises(db.SchemaBehindError, match="expects 99999999999999"):
        db.check_schema(conn, "99999999999999")


def test_seeded_instruments(conn: Conn) -> None:
    symbols = [i.symbol for i in db.list_instruments(conn)]
    assert symbols == ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD"]
    assert db.get_instrument(conn, "USD/JPY").pip_size == Decimal("0.01")


def test_rule_params_resolution_order(conn: Conn) -> None:
    eur = db.get_instrument(conn, "EUR/USD")
    assert db.rule_params(conn, "fib_pivot.levels") == {"min_fib": 13, "max_fib": 987}
    conn.execute(
        "INSERT INTO strategy_param_overrides (key, instrument_id, params) VALUES (%s, %s, %s)",
        ("fib_pivot.levels", eur.id, Jsonb({"min_fib": 89})),
    )
    assert db.rule_params(conn, "fib_pivot.levels", eur.id) == {"min_fib": 89, "max_fib": 987}
    gbp = db.get_instrument(conn, "GBP/USD")
    assert db.rule_params(conn, "fib_pivot.levels", gbp.id)["min_fib"] == 13
    with pytest.raises(LookupError):
        db.rule_params(conn, "no.such_rule")


def _daily_fixture() -> list[Candle]:
    raw = load_fixture("http/oanda_candles_d.json")["candles"]
    return [parse_candle("EUR_USD", "D", c) for c in raw]


def test_upsert_candles_stores_only_complete(conn: Conn) -> None:
    eur = db.get_instrument(conn, "EUR/USD")
    assert db.upsert_candles(conn, eur.id, _daily_fixture()) == 1
    assert db.latest_candle_ts(conn, eur.id, "D") == datetime(2026, 9, 28, 21, tzinfo=UTC)


def test_levels_computed_from_the_prior_trading_day(conn: Conn) -> None:
    eur = db.get_instrument(conn, "EUR/USD")
    db.upsert_candles(conn, eur.id, _daily_fixture())
    # Weekly candle for the week before 2026-09-28; monthly candle for August.
    week = datetime(2026, 9, 20, 21, tzinfo=UTC)
    month = datetime(2026, 7, 31, 21, tzinfo=UTC)
    db.upsert_candles(
        conn,
        eur.id,
        [
            Candle(instrument="EUR_USD", granularity="W", ts=week, o=Decimal("1.08"),
                   h=Decimal("1.09500"), l=Decimal("1.07500"), c=Decimal("1.08800"),
                   volume=1, complete=True),
            Candle(instrument="EUR_USD", granularity="M", ts=month, o=Decimal("1.08"),
                   h=Decimal("1.11000"), l=Decimal("1.06000"), c=Decimal("1.09000"),
                   volume=1, complete=True),
        ],
    )  # fmt: skip

    # The completed daily candle opened Monday 17:00 New York, so it is Tuesday's trading
    # day; its levels apply to Wednesday 2026-09-30.
    assert trading_day_start(date(2026, 9, 29)) == datetime(2026, 9, 28, 21, tzinfo=UTC)
    compute_and_store(conn, eur, date(2026, 9, 30))
    stored = db.get_levels(conn, eur.id, date(2026, 9, 30))

    assert set(stored) == {"daily", "prev_day", "fib_pivot", "weekly", "monthly"}
    fx = load_fixture("floor_pivots_basic.json")["cases"][0]["expected"]
    for name, value in fx.items():
        assert round(Decimal(str(stored["daily"][name])), 5) == Decimal(value), name
    assert stored["prev_day"] == {
        "PDH": 1.0895,
        "PDL": 1.0829,
        "PDC": 1.087,
        "source": stored["prev_day"]["source"],
    }
    ladder = load_fixture("fib_pivot_eurusd.json")["expected"]
    assert stored["fib_pivot"]["fib"] == ladder["fib"]
    for side in ("up", "down"):
        for name, value in ladder[side].items():
            assert Decimal(str(stored["fib_pivot"][side][name])) == Decimal(value)
    assert stored["weekly"]["source"]["ts"] == week.isoformat()
    assert stored["monthly"]["source"]["ts"] == month.isoformat()


def test_levels_use_per_instrument_override(conn: Conn) -> None:
    eur = db.get_instrument(conn, "EUR/USD")
    db.upsert_candles(conn, eur.id, _daily_fixture())
    conn.execute(
        "INSERT INTO strategy_param_overrides (key, instrument_id, params) VALUES (%s, %s, %s)",
        ("fib_pivot.levels", eur.id, Jsonb({"min_fib": 89})),
    )
    sets = compute_and_store(conn, eur, date(2026, 9, 30))
    assert sets["fib_pivot"]["fib"] == 89
    assert sets["fib_pivot"]["offsets"] == [89, 144, 233, 377]


class FakeOanda:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, datetime]] = []

    def history(
        self, instrument: str, granularity: str, start: datetime, end: datetime | None = None
    ) -> list[Candle]:
        self.requests.append((instrument, granularity, start))
        return _daily_fixture() if granularity == "D" and instrument == "EUR_USD" else []


def test_backfill_forex(conn: Conn) -> None:
    eur = db.get_instrument(conn, "EUR/USD")
    fake = FakeOanda()
    detail = backfill_forex(conn, fake, [eur], datetime(2026, 9, 30, 12, tzinfo=UTC))  # type: ignore[arg-type]

    grans = {g for _, g, _ in fake.requests}
    assert grans == {"M15", "D", "W", "M"}
    starts = {g: s for _, g, s in fake.requests}
    assert starts["D"] == datetime(2025, 8, 26, 12, tzinfo=UTC)  # 400 days
    assert starts["M15"].astimezone(UTC).hour in (21, 22)  # a trading day open
    assert detail["instruments"]["EUR/USD"]["candles"]["D"] == 1
    assert "daily" in db.get_levels(conn, eur.id, date(2026, 9, 30))

    row = conn.execute(
        "SELECT job, ok, finished_at IS NOT NULL FROM job_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row == ("backfill", True, True)


def _bar(ticker: str, d: date, c: str = "10") -> DailyBar:
    p = Decimal(c)
    return DailyBar(ticker=ticker, session_date=d, o=p, h=p, l=p, c=p, volume=1000)


class FakeMassive:
    def __init__(self, published: set[date]) -> None:
        self.published = published
        self.grouped_calls: list[date] = []

    def grouped_daily(self, session_date: date) -> list[DailyBar]:
        self.grouped_calls.append(session_date)
        if session_date not in self.published:
            return []
        return [_bar("AAPL", session_date), _bar("IBM", session_date)]

    def ticker_history(self, ticker: str, start: date, end: date) -> list[DailyBar]:
        return [_bar(ticker, date(2026, 9, 25), "4.55"), _bar(ticker, date(2026, 9, 29), "9.10")]

    def splits_on(self, session_date: date) -> list[Split]:
        return [
            Split(ticker="CAMP", execution_date=session_date,
                  split_from=Decimal(1), split_to=Decimal(2)),
        ]  # fmt: skip

    def active_common_stocks(self) -> list[TickerRef]:
        return [TickerRef(ticker="AAPL", name="Apple", exchange="XNAS")]


def test_backfill_stocks_resumes_and_records_progress(conn: Conn) -> None:
    conn.execute("INSERT INTO market_holidays (day, market) VALUES ('2026-09-07', 'us_stocks')")
    conn.execute("INSERT INTO stock_tickers (ticker, active) VALUES ('GONE', true), ('AAPL', true)")
    published = {date(2026, 9, 25), date(2026, 9, 28)}
    fake = FakeMassive(published)
    today = date(2026, 9, 30)

    detail = backfill_stocks(conn, fake, today, sessions=3)
    assert fake.grouped_calls == [date(2026, 9, 29), date(2026, 9, 28), date(2026, 9, 25)]
    assert detail["loaded"] == 2
    assert detail["empty_sessions"] == ["2026-09-29"]
    assert detail["tickers"] == {"active": 1, "retired": 1}

    fake.grouped_calls.clear()
    detail = backfill_stocks(conn, fake, today, sessions=3)
    assert fake.grouped_calls == [date(2026, 9, 29)]  # only the session not yet stored
    assert detail["already_stored"] == 2

    active = conn.execute("SELECT ticker FROM stock_tickers WHERE active ORDER BY 1").fetchall()
    assert active == [("AAPL",)]


def test_split_refetch_replaces_history(conn: Conn) -> None:
    db.upsert_stock_bars(
        conn, [_bar("CAMP", date(2026, 9, 24), "9.00"), _bar("CAMP", date(2026, 9, 25), "9.10")]
    )
    tickers = refetch_split_tickers(conn, FakeMassive(set()), date(2026, 9, 29))
    assert tickers == ["CAMP"]
    rows = conn.execute(
        "SELECT session_date, c FROM stock_daily_bars WHERE ticker = 'CAMP' ORDER BY 1"
    ).fetchall()
    assert rows == [
        (date(2026, 9, 25), Decimal("4.550000")),
        (date(2026, 9, 29), Decimal("9.100000")),
    ]


def test_rules_snapshot_matches_the_database(conn: Conn) -> None:
    """Strategy tests read tests/fixtures/rules_snapshot.json; it must match the migrations.
    Regenerate it after a rule migration."""
    from scanner.rules.registry import load_ruleset  # noqa: PLC0415

    rs = load_ruleset(conn)
    live = {k: rs.rule(k).model_dump() for k in sorted(rs.version_set())}
    assert live == load_fixture("rules_snapshot.json")["rules"]


def test_instruments_without_history(conn: Conn) -> None:
    pending = {i.symbol for i in db.instruments_without_history(conn)}
    eur = next(i for i in db.list_instruments(conn) if i.symbol == "EUR/USD")
    db.upsert_candles(conn, eur.id, _daily_fixture())
    after = {i.symbol for i in db.instruments_without_history(conn)}
    assert "EUR/USD" in pending and "EUR/USD" not in after
    conn.execute("UPDATE instruments SET enabled = false WHERE symbol = 'GBP/USD'")
    assert "GBP/USD" not in {i.symbol for i in db.instruments_without_history(conn)}
