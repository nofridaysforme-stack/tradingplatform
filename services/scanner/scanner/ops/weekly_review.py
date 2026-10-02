"""Paper-run weekly review (spec 17): what the owners go through together each week.

    uv run python -m scanner.ops.weekly_review                      # the last 7 days
    uv run python -m scanner.ops.weekly_review --since 2026-11-02   # cumulative since a date

- Signals created, by strategy and pair
- Outcomes of signals that closed, with the backtest's definitions (scanner.backtest.metrics)
- Alerts sent, by channel and per owner per trading day (is the volume comfortable?)
- 3/8 indicators: how often each fired in closed signals and the results when it did, the
  evidence for approving, changing, or disabling a provisional rule
- Notes and invalidations, with who wrote them

Reads only; it changes nothing.
"""

import argparse
import sys
from collections import Counter, defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from scanner import db
from scanner.backtest.metrics import Summary, summarize
from scanner.config import Settings
from scanner.time import is_forex_trading_day, to_new_york, trading_day_of, trading_day_start

STRATEGY_NAMES = {"three_eight": "3/8 system", "fib_pivot": "Fib Pivot"}
CLOSED_STATES = ("target_hit", "stop_hit", "expired", "ambiguous")


@dataclass(frozen=True)
class SignalRow:
    id: str
    strategy: str
    symbol: str
    direction: str
    state: str
    result_pips: float | None
    created_at: datetime
    closed_at: datetime | None


@dataclass(frozen=True)
class IndicatorHit:
    signal_id: str
    key: str
    fired: bool
    provisional: bool


@dataclass(frozen=True)
class RuleInfo:
    name: str
    status: str


@dataclass(frozen=True)
class AlertRow:
    user_id: str | None
    kind: str
    channel: str


@dataclass(frozen=True)
class NoteRow:
    at: datetime
    kind: str
    strategy: str
    symbol: str
    note: str
    author: str | None


@dataclass(frozen=True)
class IndicatorStat:
    key: str
    name: str
    status: str
    fired: int
    share: float
    when_fired: Summary


@dataclass
class Review:
    start: datetime
    end: datetime
    trading_days: int
    created: dict[tuple[str, str], Counter[str]]
    outcomes: dict[str, Summary]
    states: dict[str, Counter[str]]
    invalidated: int
    alerts: Counter[str]
    owners_alerted: int
    indicators: list[IndicatorStat]
    notes: list[NoteRow]
    open_now: int
    remarks: list[str] = field(default_factory=list)


def forex_days_between(start: datetime, end: datetime, holidays: Collection[date] = ()) -> int:
    """Trading days that overlap [start, end), counting a partly covered day."""
    day, last = trading_day_of(start), trading_day_of(end - timedelta(microseconds=1))
    n = 0
    while day <= last:
        n += is_forex_trading_day(day, holidays)
        day += timedelta(days=1)
    return n


def closed_in(signals: Sequence[SignalRow], start: datetime, end: datetime) -> list[SignalRow]:
    return [
        s
        for s in signals
        if s.state in CLOSED_STATES
        and s.result_pips is not None
        and s.closed_at is not None
        and start <= s.closed_at < end
    ]


def indicator_stats(
    closed: Sequence[SignalRow], hits: Sequence[IndicatorHit], rules: dict[str, RuleInfo]
) -> list[IndicatorStat]:
    """For closed 3/8 signals: per indicator, how often it fired and the results when it did.
    Same idea as the backtest's indicator_frequency, on live signals."""
    three_eight = {s.id: s for s in closed if s.strategy == "three_eight"}
    fired: dict[str, list[SignalRow]] = defaultdict(list)
    seen: dict[str, bool] = {}
    for h in hits:
        if h.signal_id not in three_eight:
            continue
        seen[h.key] = seen.get(h.key, False) or h.provisional
        if h.fired:
            fired[h.key].append(three_eight[h.signal_id])
    out = []
    for key, provisional_then in seen.items():
        rule = rules.get(key, RuleInfo(key, "provisional" if provisional_then else "approved"))
        rows = fired.get(key, [])
        out.append(
            IndicatorStat(
                key=key,
                name=rule.name,
                status=rule.status,
                fired=len(rows),
                share=round(len(rows) / len(three_eight), 3) if three_eight else 0.0,
                when_fired=summarize([(s.state, float(s.result_pips or 0)) for s in rows]),
            )
        )
    # Provisional rules first: they are the ones waiting for a decision.
    return sorted(out, key=lambda r: (r.status != "provisional", -r.fired, r.name))


def build(
    start: datetime,
    end: datetime,
    signals: Sequence[SignalRow],
    hits: Sequence[IndicatorHit],
    rules: dict[str, RuleInfo],
    alerts: Sequence[AlertRow],
    notes: Sequence[NoteRow],
    holidays: Collection[date] = (),
) -> Review:
    created: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for s in signals:
        if start <= s.created_at < end:
            created[(s.strategy, s.symbol)][s.direction] += 1
    closed = closed_in(signals, start, end)
    by_strategy: dict[str, list[SignalRow]] = defaultdict(list)
    for s in closed:
        by_strategy[s.strategy].append(s)
    outcomes = {
        k: summarize([(s.state, float(s.result_pips or 0)) for s in v])
        for k, v in sorted(by_strategy.items())
    }
    states = {k: Counter(s.state for s in v) for k, v in sorted(by_strategy.items())}
    invalidated = sum(
        1
        for s in signals
        if s.state == "invalidated" and s.closed_at is not None and start <= s.closed_at < end
    )
    review = Review(
        start=start,
        end=end,
        trading_days=forex_days_between(start, end, holidays),
        created=dict(sorted(created.items())),
        outcomes=outcomes,
        states=states,
        invalidated=invalidated,
        alerts=Counter(a.channel for a in alerts),
        owners_alerted=len({a.user_id for a in alerts if a.user_id}),
        indicators=indicator_stats(closed, hits, rules),
        notes=sorted(notes, key=lambda n: n.at),
        open_now=sum(1 for s in signals if s.state in ("open", "confirmed")),
    )
    small = [r for r in review.indicators if r.status == "provisional" and r.fired < 30]
    if small:
        review.remarks.append(
            "Provisional indicators that fired fewer than 30 times: "
            + ", ".join(r.name for r in small)
            + ". Run with --since <first day of the paper run> to see all the evidence so far."
        )
    return review


def _ny(ts: datetime) -> str:
    return to_new_york(ts).strftime("%a %b %d %H:%M") + " NY"


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _pf(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]], right: set[int]) -> list[str]:
    widths = [max(len(str(c)) for c in col) for col in zip(header, *rows, strict=False)]

    def fmt(row: Sequence[str]) -> str:
        cells = [
            str(c).rjust(w) if i in right else str(c).ljust(w)
            for i, (c, w) in enumerate(zip(row, widths, strict=True))
        ]
        return "  " + "  ".join(cells).rstrip()

    return [fmt(header), *[fmt(r) for r in rows]]


def render(r: Review) -> str:
    lines = [
        "Paper run weekly review",
        f"Window: {_ny(r.start)} to {_ny(r.end)} ({r.trading_days} forex trading days)",
        "Prices are reference prices, before any broker spread.",
        "",
        "Signals created",
    ]
    if r.created:
        rows = [
            [STRATEGY_NAMES.get(st, st), sym, str(sum(c.values())), str(c["long"]), str(c["short"])]
            for (st, sym), c in r.created.items()
        ]
        total = sum(sum(c.values()) for c in r.created.values())
        lines += _table(["Strategy", "Pair", "Signals", "Long", "Short"], rows, {2, 3, 4})
        per_day = total / r.trading_days if r.trading_days else 0.0
        lines.append(f"  {total} in total, {per_day:.1f} per trading day")
    else:
        lines.append("  None")
    lines += ["", "Outcomes of signals that closed"]
    if r.outcomes:
        rows = []
        for st, s in r.outcomes.items():
            c = r.states[st]
            rows.append([
                STRATEGY_NAMES.get(st, st), str(s.trades), str(s.wins), _pct(s.win_rate),
                f"{s.net_pips:+.1f}", f"{s.expectancy:+.2f}", _pf(s.profit_factor),
                str(c["expired"]), str(c["ambiguous"]),
            ])  # fmt: skip
        lines += _table(
            ["Strategy", "Closed", "Wins", "Win rate", "Net pips", "Per trade", "PF", "Expired",
             "Ambiguous"],
            rows, {1, 2, 3, 4, 5, 6, 7, 8},
        )  # fmt: skip
    else:
        lines.append("  None")
    lines.append(
        f"  Marked invalid: {r.invalidated} (left out of the numbers). Still open: {r.open_now}"
    )
    lines += ["", "Alerts sent (signals and updates)"]
    if r.alerts:
        sent = sum(r.alerts.values())
        by = ", ".join(f"{ch} {n}" for ch, n in sorted(r.alerts.items()))
        lines.append(f"  {sent} sent: {by}")
        if r.owners_alerted and r.trading_days:
            per = sent / r.owners_alerted / r.trading_days
            lines.append(f"  {per:.1f} per owner per trading day across {r.owners_alerted} owners")
    else:
        lines.append("  None")
    lines += ["", "3/8 indicators in closed signals (provisional first)"]
    if r.indicators:
        rows = [
            [i.name, i.status, str(i.fired), _pct(i.share),
             _pct(i.when_fired.win_rate) if i.fired else "n/a",
             f"{i.when_fired.expectancy:+.2f}" if i.fired else "n/a"]
            for i in r.indicators
        ]  # fmt: skip
        lines += _table(
            ["Indicator", "Status", "Fired", "Share", "Win rate", "Per trade"], rows, {2, 3, 4, 5}
        )
        overall = r.outcomes.get("three_eight")
        if overall:
            lines.append(
                f"  All closed 3/8 signals: win rate {_pct(overall.win_rate)}, "
                f"{overall.expectancy:+.2f} pips per trade"
            )
    else:
        lines.append("  None")
    lines += ["", "Notes and invalidations"]
    if r.notes:
        for n in r.notes:
            what = "Marked invalid" if n.kind == "invalidated" else "Note"
            who = f" ({n.author})" if n.author else ""
            sig = f"{STRATEGY_NAMES.get(n.strategy, n.strategy)} {n.symbol}"
            lines.append(f"  {_ny(n.at)}  {sig}  {what}{who}: {n.note}")
    else:
        lines.append("  None")
    if r.remarks:
        lines += ["", *[f"Note: {x}" for x in r.remarks]]
    return "\n".join(lines)


@dataclass(frozen=True)
class Loaded:
    signals: list[SignalRow]
    hits: list[IndicatorHit]
    rules: dict[str, RuleInfo]
    alerts: list[AlertRow]
    notes: list[NoteRow]


def load(conn: db.Conn, start: datetime, end: datetime) -> Loaded:
    signals = [
        SignalRow(
            str(r[0]),
            r[1],
            r[2] or "",
            r[3],
            r[4],
            float(r[5]) if r[5] is not None else None,
            r[6],
            r[7],
        )
        for r in conn.execute(
            "SELECT s.id, s.strategy::text, i.symbol, s.direction::text, s.state::text, "
            "s.result_pips, s.created_at, s.closed_at FROM signals s "
            "LEFT JOIN instruments i ON i.id = s.instrument_id "
            "WHERE (s.created_at >= %s AND s.created_at < %s) "
            "OR (s.closed_at >= %s AND s.closed_at < %s) OR s.state IN ('open', 'confirmed')",
            (start, end, start, end),
        ).fetchall()
    ]
    ids = [s.id for s in signals]
    hits = [
        IndicatorHit(str(r[0]), r[1], r[2], r[3])
        for r in conn.execute(
            "SELECT signal_id, key, fired, provisional FROM signal_indicators "
            "WHERE signal_id = ANY(%s::uuid[])",
            (ids,),
        ).fetchall()
    ]
    rules = {
        r[0]: RuleInfo(r[1], r[2])
        for r in conn.execute(
            "SELECT d.key, d.name, v.status::text FROM rule_definitions d "
            "JOIN rule_versions v ON v.key = d.key AND v.version = d.current_version"
        ).fetchall()
    }
    alerts = [
        AlertRow(str(r[0]) if r[0] else None, r[1], r[2])
        for r in conn.execute(
            "SELECT user_id, kind, channel::text FROM notifications "
            "WHERE status = 'sent' AND kind IN ('signal', 'update') "
            "AND created_at >= %s AND created_at < %s",
            (start, end),
        ).fetchall()
    ]
    notes = [
        NoteRow(*r)
        for r in conn.execute(
            "SELECT e.at, e.kind, s.strategy::text, coalesce(i.symbol, ''), e.note, "
            "(SELECT u.email FROM audit_log a JOIN users u ON u.id = a.user_id "
            "  WHERE a.target = s.id::text "
            "  AND a.action = CASE e.kind WHEN 'note' THEN 'signal.note' "
            "                 ELSE 'signal.invalidate' END "
            "  AND coalesce(a.after->>'note', a.after->>'reason') = e.note "
            "  ORDER BY abs(extract(epoch FROM a.at - e.at)) LIMIT 1) "
            "FROM signal_events e JOIN signals s ON s.id = e.signal_id "
            "LEFT JOIN instruments i ON i.id = s.instrument_id "
            "WHERE e.kind IN ('note', 'invalidated') AND e.at >= %s AND e.at < %s",
            (start, end),
        ).fetchall()
    ]
    return Loaded(signals, hits, rules, alerts, notes)


def window(now: datetime, days: int, since: date | None) -> tuple[datetime, datetime]:
    if since is not None:
        return trading_day_start(since), now
    return now - timedelta(days=days), now


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--days", type=int, default=7, help="days to look back (default 7)")
    group.add_argument("--since", type=date.fromisoformat, help="first trading day, YYYY-MM-DD")
    args = parser.parse_args(argv)
    settings = Settings()
    now = datetime.now(UTC)
    start, end = window(now, args.days, args.since)
    with db.make_pool(settings.database_url, max_size=1) as pool, pool.connection() as conn:
        holidays = db.holidays(conn, "forex")
        data = load(conn, start, end)
    review = build(
        start, end, data.signals, data.hits, data.rules, data.alerts, data.notes, holidays
    )
    print(render(review))
    return 0


if __name__ == "__main__":
    sys.exit(main())
