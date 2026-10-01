"""The first backtest's sweeps (spec 12, "Questions the first backtest must answer"), as
agreed with Jana on 2026-10-01. Each configuration changes one thing from the seeded rules.

    uv run python -m scanner.backtest.sweeps --start 2016-01-01 --report out/sweeps

Writes one folder per configuration (report.html, trades.csv, settings.json) and a summary
(summary.csv, summary.html) comparing them, in-sample and out-of-sample.
"""

import argparse
import csv
import html
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scanner.backtest import report
from scanner.backtest.metrics import split
from scanner.backtest.run import (
    add_common,
    build_jobs,
    ensure_history,
    load_inputs,
    oanda_source,
    run_config,
    settings_record,
    window,
)
from scanner.main import configure_logging
from scanner.rules.registry import derive

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Sweep:
    name: str
    question: str
    params: dict[str, dict[str, Any]] = field(default_factory=dict)
    disabled: frozenset[str] = frozenset()


T = "three_eight."
SWEEPS = [
    Sweep("baseline", "Seeded rules, as the documents state them"),
    Sweep("target_max_60", "Target band", {T + "target": {"daily_target_max_pips": 60}}),
    Sweep("target_max_50", "Target band", {T + "target": {"daily_target_max_pips": 50}}),
    Sweep("target_max_40", "Target band", {T + "target": {"daily_target_max_pips": 40}}),
    Sweep(
        "fib_stop_opposite_break",
        "Fib Pivot stop",
        {"fib_pivot.stop": {"stop_at": "opposite_break"}},
    ),
    Sweep(
        "trendlines_off", "Provisional indicators", disabled=frozenset({T + "trendline_channel"})
    ),
    Sweep("flags_off", "Provisional indicators", disabled=frozenset({T + "flag_pennant_triangle"})),
    Sweep(
        "window_alternative",
        "Trading window",
        {
            T + "trading_window": {"window": "alternative"},
            "fib_pivot.window": {"window": "alternative"},
        },
    ),
    Sweep("min_indicators_4", "Minimum indicators", {T + "min_indicators": {"minimum": 4}}),
    Sweep("swing_15", "Swing threshold", {T + "swing": {"threshold_pips": 15}}),
    Sweep("swing_30", "Swing threshold", {T + "swing": {"threshold_pips": 30}}),
]
SUMMARY_FIELDS = [
    "config",
    "question",
    "pair",
    "strategy",
    "sample",
    "trades",
    "win_rate",
    "expectancy",
    "profit_factor",
    "net_pips",
    "max_drawdown",
    "trades_per_week",
    "enough_trades",
]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m scanner.backtest.sweeps",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--only", help="comma separated configuration names")
    add_common(parser)
    args = parser.parse_args(argv)
    configure_logging()

    start, end = window(args)
    pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]
    inputs = load_inputs(args, start, end)
    by_symbol = {i.symbol: i for i in inputs.instruments}
    ensure_history(
        oanda_source(args.offline), [by_symbol[p] for p in pairs], start, end, args.cache
    )
    chosen = [s for s in SWEEPS if not args.only or s.name in args.only.split(",")]
    rows: list[dict[str, Any]] = []
    strategies = ("three_eight", "fib_pivot")
    for sweep in chosen:
        log.info("sweep", extra={"config": sweep.name})
        rules = derive(inputs.rules, sweep.params, set(sweep.disabled))
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
        changed = sweep.params | {k: {"enabled": False} for k in sweep.disabled}
        settings = settings_record(args, rules, strategies, start, end, jobs, changed)
        report.write(args.report / sweep.name, runs, settings, f"Backtest sweep: {sweep.name}")
        for run in runs:
            for strategy, trades in run.by_strategy().items():
                ins, outs, _ = split(trades, run.start, run.end)
                for sample, m in (("in", ins), ("out", outs)):
                    rows.append(
                        {
                            "config": sweep.name,
                            "question": sweep.question,
                            "pair": run.result.instrument,
                            "strategy": strategy,
                            "sample": sample,
                            "trades": m.trades,
                            "win_rate": m.win_rate,
                            "expectancy": m.expectancy,
                            "profit_factor": m.profit_factor,
                            "net_pips": m.net_pips,
                            "max_drawdown": m.max_drawdown,
                            "trades_per_week": m.trades_per_week,
                            "enough_trades": m.enough_trades,
                        }
                    )
    write_summary(args.report, rows)


def write_summary(out: Path, rows: list[dict[str, Any]]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "summary.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        w.writerows(rows)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(r[k]))}</td>" for k in SUMMARY_FIELDS) + "</tr>"
        for r in rows
    )
    head = "".join(f"<th>{k.replace('_', ' ')}</th>" for k in SUMMARY_FIELDS)
    (out / "summary.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Backtest sweeps</title>"
        "<style>body{font:13px system-ui;margin:16px}"
        "td,th{padding:3px 6px;border-bottom:1px solid #ddd;text-align:left}</style>"
        "<h1>Backtest sweeps</h1><p>Each folder holds the full report for "
        f"one configuration.</p><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )


if __name__ == "__main__":
    main()
