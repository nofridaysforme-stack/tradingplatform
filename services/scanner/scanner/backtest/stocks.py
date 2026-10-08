"""Stock system backtest (spec 12, spec 08 revised 2026-10-08).

Replays the momentum funnel on every stored session with the live code
(strategies/stock_momentum.py): watch list entries, buys on the indicator vote, and exits by
the fixed stop, the trailing stop, or the sell vote. One position per stock at a time.

Caution in every report: the data excludes delisted companies and covers only the stored
history (about two years on the free plan), so results overstate performance.

    uv run python -m scanner.backtest.stocks --report out/stocks
    uv run python -m scanner.backtest.stocks --report out/stocks \\
        --set stocks.momentum.projection_pct=30 --disable stocks.ind_rsi
"""

import argparse
import csv
import html
import logging
import os
import statistics
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg

from scanner import db
from scanner.backtest.run import parse_sets
from scanner.main import configure_logging
from scanner.rules.registry import RuleSet, derive, load_ruleset
from scanner.strategies import stock_momentum as sm
from scanner.strategies.stock_screener import DayBar

log = logging.getLogger(__name__)
CAUTION = (
    "The stored data excludes companies that later delisted and covers only about two years, "
    "so these results overstate performance."
)


@dataclass(frozen=True)
class Trade:
    ticker: str
    buy_session: date
    entry: Decimal
    reason: str  # stopped, trailing_stopped, sold, or open
    exit_session: date | None
    exit_price: Decimal | None
    result_pct: Decimal | None
    sessions: int
    projection_reached: bool
    votes: tuple[str, ...]
    has_provisional: bool


def replay(ticker: str, bars: Sequence[DayBar], rules: RuleSet) -> tuple[list[Trade], int]:
    """The funnel over one stock's whole history. Returns its trades and watch list entries."""
    fired = sm.indicators(bars, rules)
    state = sm.WatchState()
    trades: list[Trade] = []
    joins = 0
    i = max(0, int(rules.params("stocks.history_required")["min_sessions"]) - 1)
    while i < len(bars):
        day = sm.step(ticker, bars, i, rules, state)
        joins += day.joined
        if sm.is_buy(bars, fired, day, rules):
            found = sm.buy_votes(bars, fired, i, rules)
            p = sm.plan(bars[i].c, rules)
            t = sm.track(bars, fired, i, p, rules)
            ex = t.exit
            trades.append(
                Trade(
                    ticker, bars[i].session_date, p.entry,
                    ex.kind if ex else "open",
                    bars[ex.index].session_date if ex else None,
                    ex.price if ex else None,
                    sm.result_pct(p.entry, ex.price) if ex else None,
                    t.last_index - i,
                    t.projection_index is not None,
                    tuple(v.key for v in found),
                    sm.has_provisional(found, rules),
                )
            )  # fmt: skip
            if ex is None:
                break
            i = ex.index
            state = sm.WatchState(blocked_through=i)
        i += 1
    return trades, joins


def run(
    by_ticker: dict[str, list[DayBar]],
    rules: RuleSet,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[Trade], int]:
    trades: list[Trade] = []
    joins = 0
    tickers = sorted(by_ticker)
    for n, ticker in enumerate(tickers):
        got, j = replay(ticker, by_ticker[ticker], rules)
        trades += got
        joins += j
        if on_progress and n % 250 == 0:
            on_progress(n, len(tickers))
    return trades, joins


def summarize(trades: Sequence[Trade], joins: int) -> dict[str, float | int]:
    closed = [t for t in trades if t.result_pct is not None]
    results = [float(t.result_pct) for t in closed if t.result_pct is not None]
    wins = sum(1 for r in results if r > 0)
    out: dict[str, float | int] = {
        "watch_entries": joins,
        "buys": len(trades),
        "closed": len(closed),
        "open": len(trades) - len(closed),
        "stopped": sum(1 for t in trades if t.reason == "stopped"),
        "trailing_stopped": sum(1 for t in trades if t.reason == "trailing_stopped"),
        "sold": sum(1 for t in trades if t.reason == "sold"),
        "win_rate": round(wins / len(closed), 4) if closed else 0.0,
        "average_pct": round(statistics.fmean(results) * 100, 2) if results else 0.0,
        "median_pct": round(statistics.median(results) * 100, 2) if results else 0.0,
        "average_sessions": round(statistics.fmean(t.sessions for t in closed), 1) if closed else 0,
        "projection_reached": sum(1 for t in trades if t.projection_reached),
    }
    for key in sm.INDICATORS:
        out[f"voted:{key}"] = sum(1 for t in trades if key in t.votes)
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m scanner.backtest.stocks",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--set", action="append", default=[], metavar="RULE.PARAM=VALUE")
    parser.add_argument("--disable", action="append", default=[], metavar="RULE")
    args = parser.parse_args(argv)
    configure_logging()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required (the stock bars live in the database)")
    with psycopg.connect(url) as conn:
        rules = derive(load_ruleset(conn), parse_sets(args.set), set(args.disable))
        exchanges = list(rules.params("stocks.universe")["exchanges"])
        universe = set(db.active_tickers(conn, exchanges))
        by_ticker: dict[str, list[DayBar]] = defaultdict(list)
        for ticker, d, h, low, c, v, o in db.stock_bars_since(conn, date(1900, 1, 1)):
            if ticker in universe:
                by_ticker[ticker].append(
                    DayBar(d, Decimal(h), Decimal(low), Decimal(c), int(v), Decimal(o))
                )
    trades, joins = run(by_ticker, rules, lambda n, t: log.info("replaying %s/%s", n, t))
    write(args.report, trades, joins, args.set, args.disable)


def write(
    out: Path,
    trades: Sequence[Trade],
    joins: int,
    sets: Sequence[str] = (),
    disabled: Sequence[str] = (),
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fields = [
        "ticker", "buy_session", "entry", "reason", "exit_session", "exit_price",
        "result_pct", "sessions", "projection_reached", "votes", "has_provisional",
    ]  # fmt: skip
    with (out / "stock_trades.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for t in trades:
            w.writerow([" ".join(t.votes) if k == "votes" else getattr(t, k) for k in fields])
    s = summarize(trades, joins)
    changes = [*sets, *(f"{k} off" for k in disabled)]
    varied = f"<p>Varied for this run: {html.escape(', '.join(changes))}.</p>" if changes else ""
    votes = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{s[f'voted:{k}']}</td></tr>" for k in sm.INDICATORS
    )
    (out / "stock_report.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Stock system backtest</title>"
        "<style>body{font:14px system-ui;margin:16px;max-width:760px}"
        "td,th{padding:2px 10px 2px 0;text-align:left}</style>"
        "<h1>Stock system backtest</h1>"
        f"{varied}"
        f"<p>{s['watch_entries']} watch list entries, {s['buys']} buys "
        f"({s['closed']} closed, {s['open']} still open).</p>"
        f"<p>Closed: <b>{float(s['win_rate']) * 100:.1f}%</b> won. Average result "
        f"{s['average_pct']}%, median {s['median_pct']}%, held {s['average_sessions']} sessions "
        "on average.</p>"
        f"<p>Exits: {s['stopped']} stop, {s['trailing_stopped']} trailing stop, "
        f"{s['sold']} sell signal. {s['projection_reached']} reached the projection.</p>"
        f"<table><tr><th>Indicator</th><th>Voted in buys</th></tr>{votes}</table>"
        f"<p><b>Caution.</b> {html.escape(CAUTION)}</p><p>Every trade: stock_trades.csv.</p>"
    )


if __name__ == "__main__":
    main()
