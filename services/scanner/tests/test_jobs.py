from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from scanner import db
from scanner.data.base import Candle, DailyBar, Split, TickerRef
from scanner.jobs import forex_bar_close, forex_day_roll, stock_eod
from scanner.rules.registry import Registry
from scanner.signals import store
from scanner.strategies import fib_pivot
from tests.conftest import load_fixture
from tests.strategy_kit import context

Conn = psycopg.Connection[Any]
WORKED = load_fixture("eurusd_worked_example.json")


def candle(code: str, gran: str, row: list[Any]) -> Candle:
    ts, o, h, low, c = row
    return Candle(instrument=code, granularity=gran, ts=datetime.fromisoformat(ts),
                  o=Decimal(str(o)), h=Decimal(str(h)), l=Decimal(str(low)), c=Decimal(str(c)),
                  volume=1, complete=True)  # fmt: skip


class FakeSource:
    def __init__(self, by_gran: dict[str, list[Candle]]) -> None:
        self.by_gran = by_gran
        self.calls: list[tuple[str, str]] = []

    def candles(self, instrument: str, granularity: str, start: Any = None, end: Any = None,
                count: int | None = None) -> list[Candle]:  # fmt: skip
        self.calls.append((instrument, granularity))
        return self.by_gran.get(granularity, [])


def seed_worked_example(conn: Conn) -> tuple[Any, list[Candle]]:
    eur = db.get_instrument(conn, "EUR/USD")
    bars = [candle("EUR_USD", "M15", r) for r in WORKED["bars"]]
    db.upsert_candles(conn, eur.id, bars[:-1])
    for kind, data in WORKED["levels"].items():
        db.upsert_levels(conn, eur.id, date(2026, 10, 5), kind, data)
    return eur, bars


def test_bar_close_writes_the_worked_example_signal_then_tracks_it(conn: Conn) -> None:
    eur, bars = seed_worked_example(conn)
    registry = Registry.load(conn)
    now = bars[-1].ts + timedelta(minutes=15, seconds=5)
    detail = forex_bar_close.run(conn, FakeSource({"M15": bars[-3:]}), registry, now, [eur])
    info = detail["instruments"]["EUR/USD"]
    assert info["new_bars"] == 1 and len(info["signals"]) == 1
    row = conn.execute(
        "SELECT direction, entry, stop, target, dedupe_key FROM signals WHERE id = %s",
        (info["signals"][0],),
    ).fetchone()
    assert row == ("long", Decimal("1.08420000"), Decimal("1.08190000"), Decimal("1.09050000"),
                   "three_eight:EUR/USD:long:daily.S1:2026-10-05")  # fmt: skip

    # Same bar again: nothing new, so the pair is reported stale and no duplicate is written.
    again = forex_bar_close.run(conn, FakeSource({"M15": bars[-3:]}), registry, now, [eur])
    assert again["stale"] == ["EUR/USD"]

    nxt = candle("EUR_USD", "M15", [(bars[-1].ts + timedelta(minutes=15)).isoformat(),
                                    1.0842, 1.0906, 1.0838, 1.0900])  # fmt: skip
    later = forex_bar_close.run(
        conn, FakeSource({"M15": [nxt]}), registry, now + timedelta(minutes=15), [eur]
    )
    assert later["instruments"]["EUR/USD"]["outcomes"] == 1
    state = conn.execute("SELECT state, result_pips FROM signals").fetchone()
    assert state == ("target_hit", Decimal("63.00"))


def test_bar_close_skips_when_forex_is_closed(conn: Conn) -> None:
    registry = Registry.load(conn)
    saturday = datetime(2026, 10, 3, 15, 0, 5, tzinfo=UTC)
    assert (
        forex_bar_close.run(conn, FakeSource({}), registry, saturday)["skipped"] == "market closed"
    )
    friday_close = datetime(2026, 10, 2, 21, 0, 5, tzinfo=UTC)  # 17:00:05 New York
    assert "skipped" not in forex_bar_close.run(conn, FakeSource({}), registry, friday_close, [])


def test_bar_close_respects_strategy_switches(conn: Conn) -> None:
    eur, bars = seed_worked_example(conn)
    conn.execute("UPDATE strategy_configs SET enabled = false")
    now = bars[-1].ts + timedelta(minutes=15, seconds=5)
    source = FakeSource({"M15": bars[-3:]})
    detail = forex_bar_close.run(conn, source, Registry.load(conn), now, [eur])
    assert detail["instruments"] == {} and source.calls == []


def test_day_roll_stores_levels_and_expires_fib_pivot_signals(conn: Conn) -> None:
    eur = db.get_instrument(conn, "EUR/USD")
    fx = load_fixture("fib_pivot_signal.json")
    draft = fib_pivot.evaluate(context(fx)).signals[0].model_copy(update={"instrument_id": eur.id})
    sid = store.write_signal(conn, draft)
    db.upsert_candles(conn, eur.id, [candle("EUR_USD", "M15", fx["bars"][-1])])
    daily = [candle("EUR_USD", "D", ["2026-10-04T21:00:00+00:00", 1.0850, 1.0895, 1.0829, 1.0870])]
    roll = datetime(2026, 10, 5, 21, 1, tzinfo=UTC)  # 17:01 New York
    detail = forex_day_roll.run(conn, FakeSource({"D": daily}), Registry.load(conn), roll)
    assert detail["trading_day"] == "2026-10-06"
    assert "fib_pivot" in detail["instruments"]["EUR/USD"]["level_sets"]
    assert detail["instruments"]["EUR/USD"]["expired"] == 1
    state = conn.execute("SELECT state FROM signals WHERE id = %s", (sid,)).fetchone()
    assert state == ("expired",)


class FakeMassive:
    def __init__(self, bars: list[DailyBar]) -> None:
        self.bars = bars

    def grouped_daily(self, session_date: date) -> list[DailyBar]:
        return [b for b in self.bars if b.session_date == session_date]

    def ticker_history(self, ticker: str, start: date, end: date) -> list[DailyBar]:
        return []

    def splits_on(self, session_date: date) -> list[Split]:
        return []

    def active_common_stocks(self) -> list[TickerRef]:
        return []


def test_stock_eod_screens_and_finds_alerts(conn: Conn) -> None:
    sessions: list[date] = []
    d = date(2026, 10, 5)
    while len(sessions) < 260:
        if d.weekday() < 5:
            sessions.append(d)
        d -= timedelta(days=1)
    sessions.reverse()
    history = []
    for k, s in enumerate(sessions):
        c = Decimal(str(round(3.0 + 6.0 * k / 259, 4)))
        history.append(DailyBar(ticker="RISE", session_date=s, o=c, h=c * Decimal("1.01"),
                                l=c * Decimal("0.99"), c=c, volume=500_000))  # fmt: skip
    conn.execute("INSERT INTO stock_tickers (ticker, exchange) VALUES ('RISE', 'XNAS')")
    db.upsert_stock_bars(conn, history[:-1])
    user = conn.execute(
        "INSERT INTO users (email) VALUES ('o@example.com') RETURNING id"
    ).fetchone()
    assert user is not None
    conn.execute(
        "INSERT INTO holdings (user_id, ticker, purchase_price, purchase_date) "
        "VALUES (%s, 'RISE', 5, %s)",
        (user[0], sessions[-30]),
    )
    registry = Registry.load(conn)
    not_yet = stock_eod.run(conn, FakeMassive([]), registry, sessions[-1])
    assert not_yet == {"ready": False, "session": sessions[-1].isoformat()}

    detail = stock_eod.run(conn, FakeMassive(history), registry, sessions[-1])
    assert detail["ready"] and detail["bars"] == 1
    assert detail["confirmed"] == 1 and detail["digest"] == ["RISE"]
    assert detail["holdings"][0]["alert"] == "target_reached"
    status = conn.execute(
        "SELECT status FROM stock_screen_results WHERE ticker = 'RISE'"
    ).fetchone()
    assert status == ("trend_confirmed",)


def test_retention_runs(conn: Conn) -> None:
    conn.execute(
        "INSERT INTO job_runs (job, started_at, detail) "
        "VALUES ('old', now() - interval '91 days', %s)",
        (Jsonb({}),),
    )
    assert db.apply_retention(conn)["job_runs"] == 1
