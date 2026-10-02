"""Stock screener hit rate (spec 12).

Runs the live screener on each stored session. For every stock that becomes trend
confirmed (and was not confirmed in the prior cooldown sessions), checks whether its
high reached the sales target (30 percent above that close, from stocks.sales_target)
within the next horizon sessions (20).

Caution in every report: the data excludes delisted companies and covers only the stored
history (about two years on the free plan), so results overstate performance.

    uv run python -m scanner.backtest.stocks --report out/stocks
"""

import argparse
import csv
import html
import logging
import os
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg

from scanner import db
from scanner.main import configure_logging
from scanner.rules.registry import RuleSet, load_ruleset
from scanner.strategies.stock_screener import DayBar, screen

log = logging.getLogger(__name__)
CAUTION = (
    "The stored data excludes companies that later delisted and covers only about two years, "
    "so these results overstate performance."
)


@dataclass(frozen=True)
class Pick:
    ticker: str
    session: date
    close: Decimal
    target: Decimal
    hit: bool | None  # None: not enough sessions after the pick to judge
    sessions_to_hit: int | None
    best_gain: Decimal | None


def hit_rate(
    by_ticker: dict[str, list[DayBar]],
    rules: RuleSet,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[Pick]:
    sales = rules.params("stocks.sales_target")
    gain = Decimal(str(sales["expected_profit_pct"])) / 100
    horizon = int(sales["horizon_sessions"])
    cooldown = int(rules.params("stocks.alert_new_confirmed")["cooldown_sessions"])
    min_sessions = int(rules.params("stocks.history_required")["min_sessions"])
    sessions = sorted({b.session_date for bars in by_ticker.values() for b in bars})
    index = {d: k for k, d in enumerate(sessions)}
    picks: list[Pick] = []
    confirmed_at: dict[str, list[int]] = defaultdict(list)
    tickers = sorted(by_ticker)
    for n, ticker in enumerate(tickers):
        bars = by_ticker[ticker]
        for k in range(min_sessions - 1, len(bars)):
            result = screen(ticker, bars[: k + 1], rules)
            if result is None or result.status != "trend_confirmed":
                continue
            s = index[bars[k].session_date]
            recent = [p for p in confirmed_at[ticker] if s - p <= cooldown]
            confirmed_at[ticker].append(s)
            if recent:
                continue
            picks.append(_outcome(ticker, bars, k, gain, horizon))
        if on_progress and n % 250 == 0:
            on_progress(n, len(tickers))
    return picks


def _outcome(ticker: str, bars: Sequence[DayBar], k: int, gain: Decimal, horizon: int) -> Pick:
    close = bars[k].c
    target = close * (1 + gain)
    after = bars[k + 1 : k + 1 + horizon]
    best = max((b.h for b in after), default=None)
    for j, b in enumerate(after, start=1):
        if b.h >= target:
            return Pick(
                ticker,
                bars[k].session_date,
                close,
                target,
                True,
                j,
                (best - close) / close if best else None,
            )
    judged = len(after) >= horizon
    return Pick(
        ticker,
        bars[k].session_date,
        close,
        target,
        False if judged else None,
        None,
        (best - close) / close if best is not None else None,
    )


def summarize(picks: Sequence[Pick]) -> dict[str, float | int]:
    judged = [p for p in picks if p.hit is not None]
    hits = sum(1 for p in judged if p.hit)
    return {
        "picks": len(picks),
        "judged": len(judged),
        "hits": hits,
        "hit_rate": round(hits / len(judged), 4) if judged else 0.0,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m scanner.backtest.stocks",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    configure_logging()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required (the stock bars live in the database)")
    with psycopg.connect(url) as conn:
        rules = load_ruleset(conn)
        exchanges = list(rules.params("stocks.universe")["exchanges"])
        universe = set(db.active_tickers(conn, exchanges))
        by_ticker: dict[str, list[DayBar]] = defaultdict(list)
        for ticker, d, h, low, c, v in db.stock_bars_since(conn, date(1900, 1, 1)):
            if ticker in universe:
                by_ticker[ticker].append(DayBar(d, Decimal(h), Decimal(low), Decimal(c), int(v)))
    picks = hit_rate(by_ticker, rules, lambda n, t: log.info("screening %s/%s", n, t))
    write(args.report, picks)


def write(out: Path, picks: Sequence[Pick]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fields = ["ticker", "session", "close", "target", "hit", "sessions_to_hit", "best_gain"]
    with (out / "stock_picks.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for p in picks:
            w.writerow([getattr(p, k) for k in fields])
    s = summarize(picks)
    (out / "stock_report.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Stock screener hit rate</title>"
        "<style>body{font:14px system-ui;margin:16px;max-width:760px}</style>"
        "<h1>Stock screener hit rate</h1>"
        f"<p><b>{s['hit_rate'] * 100:.1f}%</b> of {s['judged']} judged picks reached the "
        f"sales target within the horizon ({s['hits']} hits; "
        f"{s['picks'] - s['judged']} picks too recent to judge).</p>"
        f"<p><b>Caution.</b> {html.escape(CAUTION)}</p><p>Every pick: stock_picks.csv.</p>"
    )
