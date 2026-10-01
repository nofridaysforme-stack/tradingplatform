"""Stock screener, Financial Wealth Building (spec 08). Pure functions over daily bars.

universe -> liquidity filter -> Rule 1 -> Rule 2 -> Rule 3 -> qualified
qualified -> five line chart -> trend status (established, confirmed) -> digest
holdings -> sales targets -> progress and alerts
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from scanner.rules.registry import RuleSet

K = "stocks."
Status = Literal["qualified", "trend_established", "trend_confirmed"]


@dataclass(frozen=True)
class DayBar:
    session_date: date
    h: Decimal
    l: Decimal  # noqa: E741
    c: Decimal
    volume: int


@dataclass(frozen=True)
class FiveLine:
    close: dict[int, Decimal]  # N -> close N sessions ago
    acc: dict[int, Decimal]  # (C0 - CN) / CN
    apr: dict[int, Decimal]  # ACC_N / N * trader_year


@dataclass(frozen=True)
class ScreenResult:
    ticker: str
    session_date: date
    status: Status
    close: Decimal
    high_52w: Decimal
    low_52w: Decimal
    apr_52w: Decimal
    five: FiveLine
    consistent: bool

    def as_row(self, version_set: dict[str, int]) -> dict[str, Any]:
        row: dict[str, Any] = {
            "session_date": self.session_date,
            "ticker": self.ticker,
            "status": self.status,
            "close": self.close,
            "high_52w": self.high_52w,
            "low_52w": self.low_52w,
            "apr_52w": self.apr_52w,
            "consistent": self.consistent,
            "version_set": version_set,
        }
        for n in (5, 10, 20, 50):
            row[f"close_{n}"] = self.five.close.get(n)
            row[f"acc_{n}"] = self.five.acc.get(n)
            row[f"apr_{n}"] = self.five.apr.get(n)
        return row


# The three rules


def rule1_near_high(close: Decimal, high_52w: Decimal, ratio: Decimal) -> bool:
    return close >= high_52w * ratio


def rule2_double(high_52w: Decimal, low_52w: Decimal, multiple: Decimal) -> bool:
    return high_52w >= low_52w * multiple


def apr_52w(high_52w: Decimal, low_52w: Decimal) -> Decimal:
    return (high_52w - low_52w) / low_52w


# Five line chart


def five_line(closes: Sequence[Decimal], periods: Sequence[int], trader_year: int) -> FiveLine:
    """closes: oldest first; the last is today's close C0."""
    c0 = closes[-1]
    close: dict[int, Decimal] = {}
    acc: dict[int, Decimal] = {}
    apr: dict[int, Decimal] = {}
    for n in periods:
        if len(closes) <= n:
            continue
        cn = closes[-1 - n]
        close[n] = cn
        acc[n] = (c0 - cn) / cn
        apr[n] = acc[n] / n * trader_year
    return FiveLine(close, acc, apr)


def screen(ticker: str, bars: Sequence[DayBar], rules: RuleSet) -> ScreenResult | None:
    """Screen one ticker on its latest session. bars: oldest first. None if not qualified."""
    if not bars:
        return None
    hist = rules.params(K + "history_required")
    if rules.enabled(K + "history_required") and len(bars) < int(hist["min_sessions"]):
        return None
    today = bars[-1]

    if rules.enabled(K + "liquidity"):
        liq = rules.params(K + "liquidity")
        recent = bars[-int(liq["avg_volume_sessions"]) :]
        avg_volume = Decimal(sum(b.volume for b in recent)) / len(recent)
        if today.c < Decimal(str(liq["min_price"])) or avg_volume < Decimal(liq["min_avg_volume"]):
            return None

    window = bars[-int(hist["lookback_sessions"]) :]
    high = max(b.h for b in window)
    low = min(b.l for b in window)
    if low <= 0:
        return None
    apr = apr_52w(high, low)
    if rules.enabled(K + "rule1_near_high") and not rule1_near_high(
        today.c, high, Decimal(str(rules.params(K + "rule1_near_high")["ratio"]))
    ):
        return None
    if rules.enabled(K + "rule2_double") and not rule2_double(
        high, low, Decimal(str(rules.params(K + "rule2_double")["multiple"]))
    ):
        return None
    if rules.enabled(K + "rule3_apr") and apr < Decimal(
        str(rules.params(K + "rule3_apr")["min_apr"])
    ):
        return None

    fl = rules.params(K + "five_line")
    five = five_line([b.c for b in bars], [int(n) for n in fl["periods"]], int(fl["trader_year"]))
    status: Status = "qualified"
    est = Decimal(str(rules.params(K + "trend_established")["min_acc"]))
    conf = Decimal(str(rules.params(K + "trend_confirmed")["min_acc"]))
    if rules.enabled(K + "trend_established") and five.acc.get(20, Decimal(-1)) > est:
        status = "trend_established"
        if rules.enabled(K + "trend_confirmed") and five.acc.get(50, Decimal(-1)) > conf:
            status = "trend_confirmed"
    cons = Decimal(str(rules.params(K + "trend_consistent")["min_acc"]))
    consistent = all(five.acc.get(n, Decimal(-1)) > cons for n in (5, 10))
    return ScreenResult(
        ticker, today.session_date, status, today.c, high, low, apr, five, consistent
    )


def digest_candidates(
    results: Sequence[ScreenResult],
    recently_confirmed: set[str],
    rules: RuleSet,
) -> list[ScreenResult]:
    """Rule stocks.alert_new_confirmed: stocks confirmed today that were not confirmed in the
    prior cooldown_sessions, best APR_20 first, at most max_in_digest."""
    p = rules.params(K + "alert_new_confirmed")
    required = rules.params(K + "trend_consistent")["required_for_alert"]
    picked = [
        r
        for r in results
        if r.status == "trend_confirmed"
        and r.ticker not in recently_confirmed
        and (r.consistent or not required)
    ]
    picked.sort(key=lambda r: r.five.apr.get(20, Decimal(0)), reverse=True)
    return picked[: int(p["max_in_digest"])]


# Holdings and sales targets


@dataclass(frozen=True)
class SalesTarget:
    target: Decimal
    earnings: Decimal
    daily: Decimal
    weekly: Decimal


def sales_target(
    purchase_price: Decimal, expected_profit_pct: Decimal, horizon_sessions: int
) -> SalesTarget:
    """Entry Points and Sales Targets: target = price x (1 + profit); daily = earnings / horizon;
    weekly = daily x 5. Unrounded; display rounds."""
    target = purchase_price * (1 + expected_profit_pct / 100)
    earnings = target - purchase_price
    daily = earnings / horizon_sessions
    return SalesTarget(target, earnings, daily, daily * 5)


@dataclass(frozen=True)
class HoldingCheck:
    progress: Decimal  # share of the planned earnings achieved
    sessions_elapsed: int
    target_reached: bool
    time_elapsed: bool


def check_holding(
    purchase_price: Decimal,
    expected_profit_pct: Decimal,
    horizon_sessions: int,
    last_close: Decimal,
    sessions_elapsed: int,
) -> HoldingCheck:
    st = sales_target(purchase_price, expected_profit_pct, horizon_sessions)
    reached = last_close >= st.target
    return HoldingCheck(
        progress=(last_close - purchase_price) / st.earnings,
        sessions_elapsed=sessions_elapsed,
        target_reached=reached,
        time_elapsed=not reached and sessions_elapsed >= horizon_sessions,
    )
