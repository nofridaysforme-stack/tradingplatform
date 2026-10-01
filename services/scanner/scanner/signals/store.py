"""Read and write signals. Every signal row is written with its indicators, version set,
and provisional flag in one transaction (CLAUDE.md rule 3)."""

import logging
from datetime import date, datetime
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from scanner import db
from scanner.signals.lifecycle import Outcome, TrackedSignal
from scanner.strategies.common import BAR, PriorSignal, SignalDraft

log = logging.getLogger(__name__)


def write_signal(conn: db.Conn, s: SignalDraft) -> UUID | None:
    """Insert a signal with its indicators and a 'created' event. Returns None when the same
    setup was already written (dedupe_key conflict): not an error (spec 10)."""
    with conn.transaction():
        row = conn.execute(
            "INSERT INTO signals (strategy, instrument_id, direction, bar_ts, trading_day, entry, "
            "stop, target, alt_target, risk_pips, reward_pips, reward_risk, indicator_count, "
            "has_provisional, is_countertrend, range_mode, version_set, context, dedupe_key) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (dedupe_key) DO NOTHING RETURNING id",
            (
                s.strategy, s.instrument_id, s.direction, s.bar_ts, s.trading_day, s.entry,
                s.stop, s.target, s.alt_target, s.risk_pips, s.reward_pips, s.reward_risk,
                s.indicator_count, s.has_provisional, s.is_countertrend, s.range_mode,
                Jsonb(s.version_set),
                Jsonb({**s.context, "explanation": s.explanation, "minimum": s.minimum,
                       "gates": [g.model_dump() for g in s.gates]}),
                s.dedupe_key,
            ),
        ).fetchone()  # fmt: skip
        if row is None:
            log.debug("duplicate signal skipped", extra={"dedupe_key": s.dedupe_key})
            return None
        signal_id: UUID = row[0]
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO signal_indicators (signal_id, key, version, fired, counted, "
                "provisional, level_ref, detail) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (signal_id, i.key, i.version, i.fired, i.counted, i.provisional,
                     i.level_ref, Jsonb(i.detail))
                    for i in s.indicators
                ],
            )  # fmt: skip
        conn.execute(
            "INSERT INTO signal_events (signal_id, at, kind, price, note) "
            "VALUES (%s, %s, 'created', %s, %s)",
            (signal_id, s.bar_ts + BAR, s.entry, s.explanation),
        )
    return signal_id


def open_signals(conn: db.Conn, instrument_id: UUID, pip_size: float) -> list[TrackedSignal]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            "SELECT s.id, s.strategy::text AS strategy, s.direction::text AS direction, "
            "s.state::text AS state, s.bar_ts, s.trading_day, s.entry, s.stop, s.target, "
            "s.context, EXISTS (SELECT 1 FROM signal_events e WHERE e.signal_id = s.id "
            "AND e.kind = 'reset_reached') AS reset_reached "
            "FROM signals s WHERE s.instrument_id = %s AND s.state IN ('open', 'confirmed') "
            "ORDER BY s.bar_ts",
            (instrument_id,),
        ).fetchall()
    out = []
    for r in rows:
        ctx = r["context"] or {}
        out.append(
            TrackedSignal(
                id=r["id"], strategy=r["strategy"], direction=r["direction"], state=r["state"],
                bar_ts=r["bar_ts"], trading_day=r["trading_day"], entry=float(r["entry"]),
                stop=float(r["stop"]), target=float(r["target"]), pip_size=pip_size,
                confirmation=ctx.get("confirmation"), reset=ctx.get("reset"),
                reset_reached=r["reset_reached"],
            )
        )  # fmt: skip
    return out


def apply_outcome(conn: db.Conn, signal_id: UUID, outcome: Outcome) -> None:
    if not outcome.events and outcome.state is None:
        return
    with conn.transaction():
        for e in outcome.events:
            conn.execute(
                "INSERT INTO signal_events (signal_id, at, kind, price, note) "
                "VALUES (%s, %s, %s, %s, %s)",
                (signal_id, e.at, e.kind, e.price, e.note),
            )
        if outcome.state is not None:
            conn.execute(
                "UPDATE signals SET state = %s, closed_at = %s, exit_price = %s, "
                "result_pips = %s WHERE id = %s",
                (outcome.state, outcome.closed_at, outcome.exit_price, outcome.result_pips,
                 signal_id),
            )  # fmt: skip


def prior_signals(conn: db.Conn, instrument_id: UUID, since: date) -> list[PriorSignal]:
    rows = conn.execute(
        "SELECT strategy::text, direction::text, bar_ts, trading_day, "
        "state NOT IN ('open', 'confirmed'), result_pips FROM signals "
        "WHERE instrument_id = %s AND trading_day >= %s AND state <> 'invalidated'",
        (instrument_id, since),
    ).fetchall()
    return [
        PriorSignal(r[0], r[1], r[2], r[3], bool(r[4]), float(r[5]) if r[5] is not None else None)
        for r in rows
    ]


def mark_confluence(
    conn: db.Conn, signal_id: UUID, s: SignalDraft, confluence_bars: int
) -> UUID | None:
    """When a 3/8 and a Fibonacci Pivot signal agree in direction on the same pair within
    confluence_bars, both carry a confluence marker. Neither signal's rules change."""
    other = "fib_pivot" if s.strategy == "three_eight" else "three_eight"
    window = BAR * confluence_bars
    row = conn.execute(
        "SELECT id FROM signals WHERE instrument_id = %s AND strategy = %s AND direction = %s "
        "AND bar_ts BETWEEN %s AND %s AND state <> 'invalidated' ORDER BY bar_ts DESC LIMIT 1",
        (s.instrument_id, other, s.direction, s.bar_ts - window, s.bar_ts + window),
    ).fetchone()
    if row is None:
        return None
    partner: UUID = row[0]
    for a, b in ((signal_id, partner), (partner, signal_id)):
        conn.execute(
            "UPDATE signals SET context = context || jsonb_build_object('confluence', %s::text) "
            "WHERE id = %s",
            (str(b), a),
        )
    return partner


def bars_since(signal_bar_ts: datetime, bar_ts: datetime) -> int:
    return int((bar_ts - signal_bar_ts) / BAR)
