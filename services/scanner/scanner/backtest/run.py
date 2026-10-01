"""Run a backtest (spec 12).

    uv run python -m scanner.backtest.run --strategy three_eight --pairs EUR/USD,GBP/USD \\
        --start 2016-01-01 --end 2026-09-30 --broker "Broker A" --report out/

Rules, pairs, broker spreads, holidays, and logged econ events come from the database when
DATABASE_URL is set (the same rule versions the live worker uses). Without a database, pass
--rules-file (the snapshot format in tests/fixtures/rules_snapshot.json); the seven seeded
pairs are used. History comes from OANDA (OANDA_API_TOKEN, OANDA_ENV) and is cached; with
--offline only the cache is read.
"""

import argparse
import json
import logging
import os
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import psycopg

from scanner import db
from scanner.backtest import history, report
from scanner.backtest.costs import SLIPPAGE, CostModel, default_spread
from scanner.backtest.engine import EngineResult, levels_from_history, run_pair
from scanner.config import OANDA_HOSTS
from scanner.data.oanda import OandaClient
from scanner.instruments import Instrument
from scanner.jobs.runtime import instrument_ref
from scanner.main import configure_logging
from scanner.rules.registry import RuleSet, derive, load_ruleset
from scanner.rules.versions import RuleVersion
from scanner.strategies.common import EconEvent

log = logging.getLogger(__name__)

SEEDED_PAIRS = [
    ("EUR/USD", "0.0001", 5),
    ("GBP/USD", "0.0001", 5),
    ("USD/JPY", "0.01", 3),
    ("USD/CHF", "0.0001", 5),
    ("USD/CAD", "0.0001", 5),
    ("AUD/USD", "0.0001", 5),
    ("NZD/USD", "0.0001", 5),
]
GRANULARITIES = ("M15", "D", "W", "M")


@dataclass
class Job:
    instrument: Instrument
    rules: RuleSet
    costs: CostModel
    strategies: tuple[str, ...]
    start: datetime
    end: datetime
    cache: Path
    holidays: frozenset[date]
    econ: tuple[EconEvent, ...]


def seeded_instruments() -> list[Instrument]:
    return [
        Instrument(
            id=uuid5(NAMESPACE_URL, f"instrument:{s}"),
            symbol=s,
            provider_code=s.replace("/", "_"),
            pip_size=Decimal(p),
            display_decimals=d,
        )
        for s, p, d in SEEDED_PAIRS
    ]


def rules_from_file(path: Path) -> RuleSet:
    data = json.loads(path.read_text())["rules"]
    return RuleSet({k: RuleVersion(**v) for k, v in data.items()})


def parse_sets(items: Sequence[str]) -> dict[str, dict[str, Any]]:
    """--set three_eight.target.daily_target_max_pips=50 -> {"three_eight.target": {...: 50}}"""
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        lhs, _, raw = item.partition("=")
        key, _, param = lhs.rpartition(".")
        try:
            value: Any = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        out.setdefault(key, {})[param] = value
    return out


def ensure_history(
    source: OandaClient | None,
    instruments: Sequence[Instrument],
    start: datetime,
    end: datetime,
    cache: Path,
) -> None:
    """Download (or confirm cached) history before the parallel runs, one pair at a time."""
    for inst in instruments:
        for gran in GRANULARITIES:
            g_start = start - timedelta(days=62) if gran in ("D", "W", "M") else start
            history.load(source, inst.provider_code, gran, g_start, end, cache)


def _run_job(job: Job) -> EngineResult:
    code = job.instrument.provider_code
    m15 = history.load(None, code, "M15", job.start, job.end, job.cache)
    lead = job.start - timedelta(days=62)
    frames = [history.load(None, code, g, lead, job.end, job.cache) for g in ("D", "W", "M")]
    if m15.empty:
        raise SystemExit(f"no cached M15 history for {job.instrument.symbol}")
    daily, weekly, monthly = frames
    levels_for = levels_from_history(
        job.instrument, daily, weekly, monthly, job.rules, job.holidays
    )
    return run_pair(
        instrument_ref(job.instrument),
        m15,
        levels_for,
        job.rules,
        job.costs,
        strategies=job.strategies,
        econ_events=job.econ,
        holidays=job.holidays,
    )


def run_config(jobs: Sequence[Job], workers: int) -> list[report.PairRun]:
    if workers <= 1 or len(jobs) == 1:
        results = [_run_job(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_run_job, jobs))
    return [report.PairRun(r, j.start, j.end) for r, j in zip(results, jobs, strict=True)]


@dataclass
class Inputs:
    rules: RuleSet
    instruments: list[Instrument]
    spreads: dict[str, float]
    holidays: frozenset[date]
    econ: tuple[EconEvent, ...]


def load_inputs(args: argparse.Namespace, start: datetime, end: datetime) -> Inputs:
    url = os.environ.get("DATABASE_URL")
    if url:
        with psycopg.connect(url) as conn:
            rules = load_ruleset(conn)
            instruments = db.list_instruments(conn, enabled_only=False)
            spreads = _broker_spreads(conn, args.broker) if args.broker else {}
            holidays = frozenset(db.holidays(conn, "forex"))
            econ = tuple(
                EconEvent(at, cur, imp) for at, cur, imp in db.econ_events(conn, start, end)
            )
    else:
        if not args.rules_file:
            raise SystemExit("set DATABASE_URL, or pass --rules-file")
        rules, instruments, spreads, holidays, econ = (
            rules_from_file(Path(args.rules_file)),
            seeded_instruments(),
            {},
            frozenset(),
            (),
        )
        if args.broker:
            raise SystemExit("--broker needs DATABASE_URL (broker profiles live in the database)")
    return Inputs(rules, instruments, spreads, holidays, econ)


def _broker_spreads(conn: db.Conn, broker: str) -> dict[str, float]:
    rows = conn.execute(
        "SELECT i.symbol, s.typical_spread_pips FROM broker_spreads s "
        "JOIN brokers b ON b.id = s.broker_id JOIN instruments i ON i.id = s.instrument_id "
        "WHERE b.name = %s",
        (broker,),
    ).fetchall()
    if not rows:
        raise SystemExit(f"no spreads for broker {broker!r}")
    return {r[0]: float(r[1]) for r in rows}


def build_jobs(
    inputs: Inputs,
    rules: RuleSet,
    pairs: Sequence[str],
    strategies: tuple[str, ...],
    start: datetime,
    end: datetime,
    cache: Path,
    spread_pips: float | None,
    slippage: float,
) -> list[Job]:
    by_symbol = {i.symbol: i for i in inputs.instruments}
    jobs = []
    for symbol in pairs:
        if symbol not in by_symbol:
            raise SystemExit(f"unknown pair {symbol}")
        spread = (
            spread_pips
            if spread_pips is not None
            else inputs.spreads.get(symbol, default_spread(symbol))
        )
        jobs.append(
            Job(
                by_symbol[symbol],
                rules,
                CostModel(spread, slippage),
                strategies,
                start,
                end,
                cache,
                inputs.holidays,
                inputs.econ,
            )
        )
    return jobs


def oanda_source(offline: bool) -> OandaClient | None:
    if offline:
        return None
    token = os.environ.get("OANDA_API_TOKEN")
    if not token:
        raise SystemExit("OANDA_API_TOKEN is not set (or use --offline to read only the cache)")
    return OandaClient(token, OANDA_HOSTS[os.environ.get("OANDA_ENV", "practice")])


def latest_complete_month() -> date:
    today = datetime.now(UTC).date()
    return today.replace(day=1)


def add_common(parser: argparse.ArgumentParser) -> None:
    seeded = ",".join(s for s, _, _ in SEEDED_PAIRS)
    parser.add_argument("--pairs", default=seeded, help="comma separated, default all seven")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2016, 1, 1))
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=None,
        help="exclusive; default the first day of this month",
    )
    parser.add_argument("--broker", help="broker profile name for spreads")
    parser.add_argument("--spread-pips", type=float, help="one spread for every pair")
    parser.add_argument("--slippage-pips", type=float, default=SLIPPAGE)
    parser.add_argument("--report", type=Path, required=True, help="output folder")
    parser.add_argument("--rules-file", help="rules snapshot JSON when DATABASE_URL is not set")
    parser.add_argument("--cache", type=Path, default=history.DEFAULT_CACHE)
    parser.add_argument("--offline", action="store_true", help="read only the cached history")
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))


def window(args: argparse.Namespace) -> tuple[datetime, datetime]:
    end = args.end or latest_complete_month()
    return (
        datetime(args.start.year, args.start.month, args.start.day, tzinfo=UTC),
        datetime(end.year, end.month, end.day, tzinfo=UTC),
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m scanner.backtest.run",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--strategy", choices=["three_eight", "fib_pivot", "both"], default="both")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="RULE.PARAM=VALUE",
        help="override a parameter for this run, e.g. three_eight.target.daily_target_max_pips=50",
    )
    parser.add_argument(
        "--disable",
        action="append",
        default=[],
        metavar="RULE",
        help="switch a rule off for this run, e.g. three_eight.trendline_channel",
    )
    add_common(parser)
    args = parser.parse_args(argv)
    configure_logging()

    start, end = window(args)
    pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]
    strategies = ("three_eight", "fib_pivot") if args.strategy == "both" else (args.strategy,)
    inputs = load_inputs(args, start, end)
    changed = parse_sets(args.set)
    rules = derive(inputs.rules, changed, set(args.disable))
    by_symbol = {i.symbol: i for i in inputs.instruments}
    ensure_history(
        oanda_source(args.offline),
        [by_symbol[p] for p in pairs if p in by_symbol],
        start,
        end,
        args.cache,
    )
    jobs = build_jobs(
        inputs,
        rules,
        pairs,
        strategies,
        start,
        end,
        args.cache,
        args.spread_pips,
        args.slippage_pips,
    )
    runs = run_config(jobs, args.workers)
    settings = settings_record(
        args,
        rules,
        strategies,
        start,
        end,
        jobs,
        changed | {k: {"enabled": False} for k in args.disable},
    )
    page = report.write(
        args.report,
        runs,
        settings,
        "Backtest: " + ", ".join(report.STRATEGY_NAMES[s] for s in strategies),
    )
    log.info("report written", extra={"path": str(page)})


def settings_record(
    args: argparse.Namespace,
    rules: RuleSet,
    strategies: Sequence[str],
    start: datetime,
    end: datetime,
    jobs: Sequence[Job],
    changed: dict[str, Any],
) -> dict[str, Any]:
    keys = [k for s in strategies for k in rules.version_set(strategy=s)]
    return {
        "start": start.date().isoformat(),
        "end": end.date().isoformat(),
        "strategies": list(strategies),
        "pairs": [j.instrument.symbol for j in jobs],
        "costs": {
            j.instrument.symbol: {
                "spread_pips": j.costs.spread_pips,
                "slippage_pips": j.costs.slippage_pips,
            }
            for j in jobs
        },
        "broker": args.broker,
        "changed": changed,
        "version_set": rules.version_set(keys),
        "params": {k: {"enabled": rules.rule(k).enabled, **rules.params(k)} for k in keys},
    }


if __name__ == "__main__":
    main()
