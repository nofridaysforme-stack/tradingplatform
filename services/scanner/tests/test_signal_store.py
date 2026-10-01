from datetime import date, timedelta
from typing import Any

import psycopg

from scanner import db
from scanner.signals import store
from scanner.signals.lifecycle import BarView, track
from scanner.strategies import fib_pivot, three_eight
from scanner.strategies.common import SignalDraft
from tests.conftest import load_fixture, ruleset_from_snapshot
from tests.strategy_kit import context

Conn = psycopg.Connection[Any]


def worked_draft(conn: Conn) -> SignalDraft:
    eur = db.get_instrument(conn, "EUR/USD")
    s = three_eight.evaluate(context(load_fixture("eurusd_worked_example.json"))).signals[0]
    return s.model_copy(update={"instrument_id": eur.id})


def test_write_signal_with_indicators_and_event(conn: Conn) -> None:
    draft = worked_draft(conn)
    sid = store.write_signal(conn, draft)
    assert sid is not None
    row = conn.execute(
        "SELECT state, entry, stop, target, reward_risk, version_set, context->>'explanation' "
        "FROM signals WHERE id = %s", (sid,),
    ).fetchone()  # fmt: skip
    assert row is not None
    assert row[0] == "open"
    assert (float(row[1]), float(row[2]), float(row[3])) == (1.0842, 1.0819, 1.0905)
    assert row[5]["three_eight.target"] == 2
    assert row[6].startswith("Long at daily S1")
    n = conn.execute(
        "SELECT count(*) FROM signal_indicators WHERE signal_id = %s", (sid,)
    ).fetchone()
    assert n is not None and n[0] == 10
    kinds = conn.execute("SELECT kind FROM signal_events WHERE signal_id = %s", (sid,)).fetchall()
    assert kinds == [("created",)]


def test_duplicate_setup_is_skipped(conn: Conn) -> None:
    draft = worked_draft(conn)
    assert store.write_signal(conn, draft) is not None
    assert store.write_signal(conn, draft) is None


def test_outcome_is_applied(conn: Conn) -> None:
    draft = worked_draft(conn)
    sid = store.write_signal(conn, draft)
    eur = db.get_instrument(conn, "EUR/USD")
    [tracked] = store.open_signals(conn, eur.id, 0.0001)
    assert tracked.id == sid
    out = track(tracked, BarView(draft.bar_ts + timedelta(minutes=15), 1.0842, 1.0906, 1.0830,
                                 1.0900), bars_since=1)  # fmt: skip
    store.apply_outcome(conn, tracked.id, out)
    row = conn.execute("SELECT state, result_pips FROM signals WHERE id = %s", (sid,)).fetchone()
    assert row is not None and row[0] == "target_hit" and float(row[1]) == 63.0
    assert store.open_signals(conn, eur.id, 0.0001) == []
    prior = store.prior_signals(conn, eur.id, date(2026, 10, 5))
    assert prior[0].closed and prior[0].result_pips == 63.0


def test_confluence_marks_both_signals(conn: Conn) -> None:
    eur = db.get_instrument(conn, "EUR/USD")
    a = worked_draft(conn)
    a_id = store.write_signal(conn, a)
    fx = load_fixture("fib_pivot_signal.json")
    b = fib_pivot.evaluate(context(fx)).signals[0].model_copy(update={"instrument_id": eur.id})
    b_id = store.write_signal(conn, b)
    assert a_id and b_id
    bars = int(ruleset_from_snapshot().params("fib_pivot.confluence")["confluence_bars"])
    assert store.mark_confluence(conn, b_id, b, bars) == a_id
    for own, other in ((a_id, b_id), (b_id, a_id)):
        row = conn.execute(
            "SELECT context->>'confluence' FROM signals WHERE id = %s", (own,)
        ).fetchone()
        assert row is not None and row[0] == str(other)
