"""Chart series for the stock page come from the same indicator code as the votes."""

from datetime import date

from scanner.charts import CHART_SESSIONS, chart_series
from scanner.strategies import stock_momentum as sm
from tests.test_stock_momentum import FAST, momentum_stock


def test_chart_series_follow_the_indicators() -> None:
    bars = momentum_stock()
    fired = sm.indicators(bars, FAST)
    s = chart_series(bars, fired, FAST)
    n = CHART_SESSIONS
    assert len(s["sessions"]) == n and s["sessions"][-1] == bars[-1].session_date.isoformat()
    assert sorted(s["ma"], key=int) == ["10", "20", "50"]
    for line in (s["ma"]["10"], s["rsi"], s["stoch_k"], s["macd"], s["volume_average"]):
        assert line is not None and len(line) == n
    # The lines are the indicators' own values, and the histogram is MACD less its signal.
    assert s["rsi"][-1] == round(float(fired["stocks.ind_rsi"].values["rsi"][-1]), 6)
    assert s["macd_histogram"][-1] == round(s["macd"][-1] - s["macd_signal"][-1], 6)
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
