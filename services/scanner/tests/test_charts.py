"""Chart series for the stock page come from the same indicator code as the votes."""

from datetime import date

from scanner.charts import CHART_SESSIONS, chart_series
from scanner.strategies import stock_momentum as sm
from tests.test_stock_momentum import FAST, momentum_stock


def test_chart_series_follow_the_indicators() -> None:
    bars = momentum_stock()
    fired = sm.indicators(bars, FAST)
    s = chart_series(bars, fired, FAST)
    n = min(CHART_SESSIONS, len(bars))  # all the history, up to about five years
    assert len(s["sessions"]) == n and s["sessions"][-1] == bars[-1].session_date.isoformat()
    assert sorted(s["ma"], key=int) == ["10", "20", "50"]
    for line in (s["ma"]["10"], s["rsi"], s["stoch_k"], s["macd"], s["volume_average"]):
        assert line is not None and len(line) == n
    # The lines are the indicators' own values, and the histogram is MACD less its signal.
    assert s["rsi"][-1] == round(float(fired["stocks.ind_rsi"].values["rsi"][-1]), 6)
    assert s["macd_histogram"][-1] == round(s["macd"][-1] - s["macd_signal"][-1], 6)
    pivot = fired["stocks.ind_pivot"].values
    assert s["pivot_ma"][-1] == round(float(pivot["pivot_ma"][-1]), 6)
    assert s["pivot_signal"][-1] == round(float(pivot["signal"][-1]), 6)
    assert s["levels"]["rsi"] == [30.0, 70.0] and s["levels"]["stoch"] == [20.0, 80.0]
    assert s["levels"]["zone_low"] == round(s["levels"]["high_52w"] * 0.9, 6)
    assert s["settings"] == {"rsi": 5, "stoch": [5, 1, 3], "macd": [12, 26, 9]}
    # The bounce that bought (spec 08 funnel test) shows as the candle's and volume's votes.
    bounce = bars[282].session_date.isoformat()
    assert bounce in s["votes"]["stocks.ind_candle"]["buy"]
    assert bounce in s["votes"]["stocks.ind_volume"]["buy"]


def test_a_switched_off_indicator_has_no_line() -> None:
    from scanner.rules.registry import derive  # noqa: PLC0415

    off = derive(FAST, disabled={"stocks.ind_rsi", "stocks.ind_ma"})
    bars = momentum_stock()
    s = chart_series(bars, sm.indicators(bars, off), off)
    assert s["rsi"] is None and "stocks.ind_rsi" not in s["votes"]
    assert list(s["ma"]) == ["50"]  # the trend line is drawn without the crossover rule


def test_short_histories_are_charted_in_full() -> None:
    bars = momentum_stock()[:60]
    s = chart_series(bars, sm.indicators(bars, FAST), FAST)
    assert len(s["sessions"]) == 60 and s["sessions"][0] == date(2024, 1, 1).isoformat()


def test_weekly_and_monthly_bars_combine_the_daily_bars() -> None:
    from decimal import Decimal  # noqa: PLC0415

    from scanner.charts import _periods  # noqa: PLC0415
    from scanner.strategies.stock_screener import DayBar  # noqa: PLC0415

    def bar(d: date, o: str, h: str, low: str, c: str, v: int) -> DayBar:
        return DayBar(d, Decimal(h), Decimal(low), Decimal(c), v, Decimal(o))

    days = [
        bar(date(2026, 10, 29), "10", "11", "9.5", "10.5", 100),  # Thursday
        bar(date(2026, 10, 30), "10.5", "12", "10", "11.5", 200),  # Friday
        bar(date(2026, 11, 2), "11.5", "11.8", "10.8", "11", 300),  # Monday, a new week and month
    ]
    week = _periods(days, "weekly")
    assert [(b.session_date, b.o, b.h, b.l, b.c, b.volume) for b in week] == [
        (date(2026, 10, 30), Decimal("10"), Decimal("12"), Decimal("9.5"), Decimal("11.5"), 300),
        (date(2026, 11, 2), Decimal("11.5"), Decimal("11.8"), Decimal("10.8"), Decimal("11"), 300),
    ]
    assert [b.session_date for b in _periods(days, "monthly")] == [
        date(2026, 10, 30),
        date(2026, 11, 2),
    ]


def test_chart_series_carries_weekly_and_monthly_views() -> None:
    bars = momentum_stock()
    s = chart_series(bars, sm.indicators(bars, FAST), FAST)
    weekly, monthly = s["weekly"], s["monthly"]
    assert len(weekly["bars"]) == len(weekly["sessions"]) == len(weekly["rsi"]) == 61
    assert weekly["bars"][-1]["time"] == bars[-1].session_date.isoformat()
    assert sum(b["volume"] for b in weekly["bars"][-2:]) == sum(b.volume for b in bars[-8:])
    assert len(monthly["bars"]) == 14  # January 2024 to February 2025
    assert monthly["macd"][-1] is None  # 14 months are too few for MACD's 26 and 9
    assert "votes" not in weekly  # the votes are on daily bars only
