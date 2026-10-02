from datetime import date, timedelta
from decimal import Decimal

import pytest

from scanner.rules.registry import RuleSet
from scanner.strategies.stock_screener import (
    DayBar,
    apr_52w,
    check_holding,
    digest_candidates,
    five_line,
    rule1_near_high,
    rule2_double,
    sales_target,
    screen,
)
from tests.conftest import load_fixture, ruleset_from_snapshot

D = Decimal
SIX = D("0.000001")


def test_five_line_example() -> None:
    fx = load_fixture("stock_five_line_example.json")
    closes = [D(fx["close_5"])] + [D("4.00")] * 4 + [D(fx["close_today"])]
    fl = five_line(closes, [5], fx["trader_year"])
    # Spec 08 truncates ACC_5 (0.3922077... shown as 0.392207); compare within one millionth.
    assert abs(fl.acc[5] - D(fx["expected"]["acc_5"])) < SIX
    assert abs(fl.apr[5] - D(fx["expected"]["apr_5"])) < SIX


def test_rules_calamp_example() -> None:
    fx = load_fixture("stock_rules_calamp.json")
    high, low, close = D(fx["high_52w"]), D(fx["low_52w"]), D(fx["close"])
    exp = fx["expected"]
    assert high * D("0.90") == D(exp["rule1_threshold"])
    assert rule1_near_high(close, high, D("0.90")) is exp["rule1"]
    assert rule2_double(high, low, D("2.0")) is exp["rule2"]
    assert apr_52w(high, low).quantize(D("0.001")) == D(exp["apr"])


def test_sales_target_example() -> None:
    fx = load_fixture("sales_target_example.json")
    st = sales_target(D(fx["purchase_price"]), D(fx["expected_profit_pct"]), fx["horizon_sessions"])
    exp = fx["expected"]
    assert (st.target, st.earnings, st.daily, st.weekly) == (
        D(exp["target"]),
        D(exp["earnings"]),
        D(exp["daily"]),
        D(exp["weekly"]),
    )


def test_holding_checks() -> None:
    reached = check_holding(D("23.13"), D(30), 20, D("30.10"), 12)
    assert reached.target_reached and not reached.time_elapsed
    late = check_holding(D("23.13"), D(30), 20, D("25.00"), 20)
    assert late.time_elapsed and not late.target_reached
    assert late.progress.quantize(D("0.01")) == D("0.27")


def _history(n: int, start: float, end: float, volume: int = 500_000) -> list[DayBar]:
    """n sessions of steady movement from start to end, oldest first."""
    out = []
    for k in range(n):
        c = D(str(round(start + (end - start) * k / (n - 1), 4)))
        out.append(
            DayBar(date(2025, 1, 1) + timedelta(days=k), c * D("1.01"), c * D("0.99"), c, volume)
        )
    return out


def test_screen_qualifies_a_doubling_stock_with_a_confirmed_trend() -> None:
    rs = ruleset_from_snapshot()
    result = screen("UP", _history(260, 3.0, 9.0), rs)
    assert result is not None
    assert result.status == "trend_confirmed"
    assert result.consistent
    assert result.apr_52w > 1
    row = result.as_row(rs.version_set(strategy="stocks"))
    assert row["acc_50"] > 0 and row["close_5"] is not None


def test_screen_filters() -> None:
    rs = ruleset_from_snapshot()
    assert screen("SHORT", _history(100, 3.0, 9.0), rs) is None  # under 252 sessions
    assert screen("FLAT", _history(260, 5.0, 5.5), rs) is None  # fails Rule 2 and Rule 3
    assert screen("THIN", _history(260, 3.0, 9.0, volume=10), rs) is None  # liquidity
    assert screen("PENNY", _history(260, 0.2, 0.9), rs) is None  # under 1.00
    down = _history(200, 9.0, 3.0) + _history(60, 3.0, 7.0)[1:]
    assert screen("DIP", down, rs) is None  # far below the 52-week high


def test_liquidity_filter_can_be_switched_off() -> None:
    rs = ruleset_from_snapshot()
    rules = {k: rs.rule(k) for k in rs._rules}
    rules["stocks.liquidity"] = rules["stocks.liquidity"].model_copy(update={"enabled": False})
    assert screen("THIN", _history(260, 3.0, 9.0, volume=10), RuleSet(rules)) is not None


def test_digest_skips_recent_and_ranks_by_apr_20() -> None:
    rs = ruleset_from_snapshot()
    fast = screen("FAST", _history(260, 3.0, 12.0), rs)
    slow = screen("SLOW", _history(260, 3.0, 9.0), rs)
    assert fast and slow
    assert [r.ticker for r in digest_candidates([slow, fast], set(), rs)] == ["FAST", "SLOW"]
    assert [r.ticker for r in digest_candidates([slow, fast], {"FAST"}, rs)] == ["SLOW"]


def test_sales_target_shared_cases() -> None:
    """The portal's TypeScript port is tested against the same cases."""
    for c in load_fixture("holding_cases.json")["cases"]:
        price, pct = Decimal(c["purchase_price"]), Decimal(c["expected_profit_pct"])
        st = sales_target(price, pct, c["horizon_sessions"])
        ck = check_holding(
            price, pct, c["horizon_sessions"], Decimal(c["last_close"]), c["sessions_elapsed"]
        )
        e = c["expected"]
        assert float(st.target) == pytest.approx(e["target"])
        assert float(st.daily) == pytest.approx(e["daily"])
        assert float(ck.progress) == pytest.approx(e["progress"])
        assert (ck.target_reached, ck.time_elapsed) == (e["target_reached"], e["time_elapsed"])
