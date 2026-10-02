"""Staging acceptance report (spec 17): checks the run against the criteria that the database
can prove, and lists what still needs a person to confirm.

    uv run python -m scanner.ops.staging_report --days 10
    uv run python -m scanner.ops.staging_report --since 2026-10-05

Exits 0 when every automatic check passes, 1 otherwise. Reads only; it changes nothing.
"""

import argparse
import sys
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise

from scanner import db
from scanner.config import Settings
from scanner.time import (
    forex_trading_days_back,
    is_forex_open,
    is_forex_trading_day,
    to_new_york,
    trading_day_end,
    trading_day_of,
    trading_day_start,
)

BAR = timedelta(minutes=15)
# The bar close job runs every 15 minutes even while the market is closed, so a longer gap
# between two runs means the scanner was down or stuck.
OUTAGE_GAP = timedelta(minutes=20)
# A run that started this long ago and never finished died with the process.
STUCK_AFTER = timedelta(minutes=15)
TEST_DELIVERY_LIMIT = timedelta(seconds=90)
REQUIRED_DAYS = 10


@dataclass(frozen=True)
class Run:
    job: str
    started_at: datetime
    finished_at: datetime | None
    ok: bool | None
    error: str | None = None


@dataclass(frozen=True)
class DeliveryCheck:
    email: str
    channel: str
    status: str
    created_at: datetime
    sent_at: datetime | None
    error: str | None = None

    @property
    def on_time(self) -> bool:
        return (
            self.status == "sent"
            and self.sent_at is not None
            and self.sent_at - self.created_at <= TEST_DELIVERY_LIMIT
        )


@dataclass(frozen=True)
class HealthAlert:
    condition: str
    first_seen_at: datetime
    last_sent_at: datetime | None
    resolved_at: datetime | None


@dataclass
class Report:
    start: datetime
    end: datetime
    trading_days: list[date]
    bar_slots: int
    missed: list[datetime]
    failures: list[Run]
    outages: list[tuple[datetime, datetime]]
    tests: list[DeliveryCheck]
    alerts: list[HealthAlert]
    notes: list[str] = field(default_factory=list)

    @property
    def checks(self) -> list[tuple[str, bool, str]]:
        late = [t for t in self.tests if not t.on_time]
        return [
            (
                f"{REQUIRED_DAYS} trading days covered",
                len(self.trading_days) >= REQUIRED_DAYS,
                f"{len(self.trading_days)} complete forex trading days in the window",
            ),
            (
                "No missed bar closes",
                self.bar_slots > 0 and not self.missed,
                f"{self.bar_slots - len(self.missed)} of {self.bar_slots} bar closes ran",
            ),
            (
                "No job failures",
                not self.failures,
                f"{len(self.failures)} failed or unfinished job runs",
            ),
            (
                "Scanner never down",
                not self.outages,
                f"{len(self.outages)} gaps of over {int(OUTAGE_GAP.total_seconds() // 60)} "
                "minutes between bar close runs",
            ),
            (
                "Test notifications within 90 seconds",
                bool(self.tests) and not late,
                f"{len(self.tests) - len(late)} of {len(self.tests)} test notifications on time",
            ),
        ]

    @property
    def passed(self) -> bool:
        return all(ok for _, ok, _ in self.checks)


def complete_trading_days(
    start: datetime, end: datetime, holidays: Collection[date] = ()
) -> list[date]:
    """Forex trading days that lie wholly inside [start, end)."""
    days: list[date] = []
    day = trading_day_of(start)
    while trading_day_start(day) < end:
        if (
            is_forex_trading_day(day, holidays)
            and trading_day_start(day) >= start
            and trading_day_end(day) <= end
        ):
            days.append(day)
        day += timedelta(days=1)
    return days


def bar_slots(start: datetime, end: datetime, holidays: Collection[date] = ()) -> list[datetime]:
    """Every 15-minute close in [start, end) that the bar close job must handle. Matches the
    job's own check: the bar that just completed belongs to an open market."""
    slot = start.replace(minute=start.minute - start.minute % 15, second=0, microsecond=0)
    if slot < start:
        slot += BAR
    out: list[datetime] = []
    while slot < end:
        if is_forex_open(slot - timedelta(minutes=1), holidays):
            out.append(slot)
        slot += BAR
    return out


def missed_slots(slots: Sequence[datetime], runs: Sequence[Run]) -> list[datetime]:
    """Slots with no successful bar close run started within the slot (retries count)."""
    done = sorted(r.started_at for r in runs if r.job == "forex_bar_close" and r.ok)
    missed: list[datetime] = []
    i = 0
    for slot in slots:
        while i < len(done) and done[i] < slot:
            i += 1
        if i == len(done) or done[i] >= slot + BAR:
            missed.append(slot)
    return missed


def failed_runs(runs: Sequence[Run], now: datetime) -> list[Run]:
    return [
        r
        for r in runs
        if r.ok is False or (r.finished_at is None and now - r.started_at > STUCK_AFTER)
    ]


def outages(runs: Sequence[Run], start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Gaps between bar close runs (open or closed market) longer than OUTAGE_GAP, including
    before the first run and after the last one."""
    marks = [start, *sorted(r.started_at for r in runs if r.job == "forex_bar_close"), end]
    return [(a, b) for a, b in pairwise(marks) if b - a > OUTAGE_GAP]


def build(
    start: datetime,
    end: datetime,
    runs: Sequence[Run],
    tests: Sequence[DeliveryCheck],
    alerts: Sequence[HealthAlert],
    holidays: Collection[date] = (),
    *,
    oanda_configured: bool = True,
) -> Report:
    slots = bar_slots(start, end, holidays)
    report = Report(
        start=start,
        end=end,
        trading_days=complete_trading_days(start, end, holidays),
        bar_slots=len(slots),
        missed=missed_slots(slots, runs),
        failures=failed_runs(runs, end),
        outages=outages(runs, start, end),
        tests=list(tests),
        alerts=list(alerts),
    )
    if not oanda_configured:
        report.notes.append(
            "OANDA_API_TOKEN is not set, so the bar close job is skipped and every bar close "
            "counts as missed. Add the key before starting the 10-day run."
        )
    if not tests:
        report.notes.append(
            "No test notifications yet. Each owner presses Send test notification in "
            "Settings, Notifications."
        )
    return report


def runs_of(slots: Sequence[datetime]) -> list[tuple[datetime, datetime, int]]:
    """Group slots 15 minutes apart into (first, last, count)."""
    out: list[tuple[datetime, datetime, int]] = []
    for s in slots:
        if out and s - out[-1][1] == BAR:
            out[-1] = (out[-1][0], s, out[-1][2] + 1)
        else:
            out.append((s, s, 1))
    return out


def _ny(ts: datetime) -> str:
    return to_new_york(ts).strftime("%a %b %d %H:%M") + " NY"


def render(report: Report) -> str:
    lines = [
        "Staging acceptance report",
        f"Window: {_ny(report.start)} to {_ny(report.end)}",
        "",
    ]
    for name, ok, detail in report.checks:
        lines.append(f"[{'pass' if ok else 'FAIL'}] {name}: {detail}")
    if report.missed:
        lines += ["", "Missed bar closes:"]
        for first, last, count in runs_of(report.missed):
            span = _ny(first) if count == 1 else f"{_ny(first)} to {_ny(last)}"
            lines.append(f"  {span} ({count} bar close{'s' if count > 1 else ''})")
    if report.failures:
        lines += ["", "Failed or unfinished job runs:"]
        for r in report.failures[:50]:
            state = "unfinished" if r.finished_at is None else (r.error or "failed")
            lines.append(f"  {_ny(r.started_at)}  {r.job}: {state}")
    if report.outages:
        lines += ["", "Scanner gaps:"]
        lines += [f"  {_ny(a)} to {_ny(b)}" for a, b in report.outages]
    late = [t for t in report.tests if not t.on_time]
    if late:
        lines += ["", "Test notifications not delivered within 90 seconds:"]
        for t in late:
            took = (
                f"{int((t.sent_at - t.created_at).total_seconds())} s"
                if t.sent_at
                else t.error or t.status
            )
            lines.append(f"  {t.email} by {t.channel}: {took}")
    if report.alerts:
        lines += ["", "Health alerts (latest occurrence of each):"]
        for a in report.alerts:
            state = f"resolved {_ny(a.resolved_at)}" if a.resolved_at else "still active"
            lines.append(f"  {a.condition}: first seen {_ny(a.first_seen_at)}, {state}")
    if report.notes:
        lines += ["", "Notes:"]
        lines += [f"  {n}" for n in report.notes]
    lines += [
        "",
        "Confirm by hand (spec 17):",
        "  Every rule shows in Settings, Rules with the right status, parameters, and source.",
        "  A rule change takes effect on the next bar and appears in the audit log.",
        "  Failure drill: stop the scanner for 10 minutes, then check the alert and Resolved.",
        "",
        "Result: " + ("all automatic checks passed" if report.passed else "not ready"),
    ]
    return "\n".join(lines)


def load(conn: db.Conn, start: datetime, end: datetime) -> tuple[list[Run], list[DeliveryCheck]]:
    runs = [
        Run(job, started, finished, ok, (detail or {}).get("error"))
        for job, started, finished, ok, detail in conn.execute(
            "SELECT job, started_at, finished_at, ok, detail FROM job_runs "
            "WHERE started_at >= %s AND started_at < %s ORDER BY started_at",
            (start, end),
        ).fetchall()
    ]
    tests = [
        DeliveryCheck(*row)
        for row in conn.execute(
            "SELECT u.email, n.channel::text, n.status::text, n.created_at, n.sent_at, n.error "
            "FROM notifications n JOIN users u ON u.id = n.user_id "
            "WHERE n.kind = 'test' AND n.created_at >= %s AND n.created_at < %s "
            "ORDER BY n.created_at",
            (start, end),
        ).fetchall()
    ]
    return runs, tests


def load_alerts(conn: db.Conn) -> list[HealthAlert]:
    return [
        HealthAlert(*row)
        for row in conn.execute(
            "SELECT condition, first_seen_at, last_sent_at, resolved_at FROM health_alerts "
            "ORDER BY first_seen_at"
        ).fetchall()
    ]


def window(
    now: datetime, days: int, since: date | None, holidays: Collection[date]
) -> tuple[datetime, datetime]:
    if since is not None:
        return trading_day_start(since), now
    # The trading day in progress is not complete, so count back from the one before it.
    last = trading_day_of(now) - timedelta(days=1)
    while not is_forex_trading_day(last, holidays):
        last -= timedelta(days=1)
    return trading_day_start(forex_trading_days_back(last, days - 1, holidays)), now


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--days", type=int, default=REQUIRED_DAYS, help="trading days to check")
    group.add_argument("--since", type=date.fromisoformat, help="first trading day, YYYY-MM-DD")
    args = parser.parse_args(argv)
    settings = Settings()
    now = datetime.now(UTC)
    with db.make_pool(settings.database_url, max_size=1) as pool, pool.connection() as conn:
        holidays = db.holidays(conn, "forex")
        start, end = window(now, args.days, args.since, holidays)
        runs, tests = load(conn, start, end)
        report = build(
            start,
            end,
            runs,
            tests,
            load_alerts(conn),
            holidays,
            oanda_configured=settings.oanda_api_token is not None,
        )
    print(render(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
