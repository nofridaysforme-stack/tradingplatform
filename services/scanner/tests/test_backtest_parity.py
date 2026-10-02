"""Spec 17 parity test: replaying a fixture day in the backtester yields the same signals
(and outcomes) as the live job path."""

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import psycopg

from scanner import db
from scanner.backtest.costs import CostModel
from scanner.backtest.engine import run_pair
from scanner.jobs import forex_bar_close
from scanner.jobs.runtime import instrument_ref
from scanner.rules.registry import Registry
from tests.conftest import load_fixture
from tests.test_jobs import FakeSource, candle

Conn = psycopg.Connection[Any]
WORKED = load_fixture("eurusd_worked_example.json")
MONDAY_OPEN = datetime.fromisoformat("2026-10-05T04:00:00+00:00")  # 00:00 New York


def fixture_rows() -> list[list[Any]]:
    rows = list(WORKED["bars"])
    last = datetime.fromisoformat(rows[-1][0])
    # Two more bars: a quiet one, then one that reaches the target.
    rows.append([(last + timedelta(minutes=15)).isoformat(), 1.0842, 1.0848, 1.0838, 1.0845])
    rows.append([(last + timedelta(minutes=30)).isoformat(), 1.0845, 1.0906, 1.0843, 1.0900])
    return rows


def test_backtest_matches_the_live_job(conn: Conn) -> None:
    eur = db.get_instrument(conn, "EUR/USD")
    for kind, data in WORKED["levels"].items():
        db.upsert_levels(conn, eur.id, MONDAY_OPEN.date(), kind, data)
    rows = fixture_rows()
    candles = [candle("EUR_USD", "M15", r) for r in rows]
    history = [c for c in candles if c.ts < MONDAY_OPEN]
    live_bars = [c for c in candles if c.ts >= MONDAY_OPEN]
    db.upsert_candles(conn, eur.id, history)

    # Live path: one new completed bar per run, as the scheduler delivers them.
    registry = Registry.load(conn)
    for c in live_bars:
        forex_bar_close.run(
            conn, FakeSource({"M15": [c]}), registry, c.ts + timedelta(minutes=15, seconds=5), [eur]
        )
    live = conn.execute(
        "SELECT dedupe_key, entry::float, stop::float, target::float, state::text, "
        "result_pips::float FROM signals ORDER BY bar_ts, dedupe_key"
    ).fetchall()

    # Backtest path: the same bars, the same rules, the same levels.
    m15 = pd.DataFrame(
        [(c.ts, float(c.o), float(c.h), float(c.l), float(c.c)) for c in candles],
        columns=["ts", "o", "h", "l", "c"],
    )
    result = run_pair(
        instrument_ref(eur), m15, lambda day: db.get_levels(conn, eur.id, day),
        registry.ruleset, CostModel(0.0, 0.0), evaluate_from=MONDAY_OPEN,
    )  # fmt: skip
    replay = sorted(
        (t.signal.dedupe_key, t.signal.entry, t.signal.stop, t.signal.target, t.state, t.gross_pips)
        for t in result.trades
    )

    assert live, "the fixture day must produce at least one signal"
    assert replay == sorted(live)
    assert (
        "three_eight:EUR/USD:long:daily.S1:2026-10-05",
        1.0842,
        1.0819,
        1.0905,
        "target_hit",
        63.0,
    ) in replay
