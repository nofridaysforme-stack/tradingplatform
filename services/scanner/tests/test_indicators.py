import numpy as np
import pytest

from scanner.indicators.base import Hit, bar_touches, direction_for_level, level_hit
from scanner.indicators.candles import candlestick_hits
from scanner.indicators.fibonacci import fibonacci_hits, retracements
from scanner.indicators.hl_failure import hl_failure_hits
from scanner.indicators.levels import pivot_hits, prev_day_hit
from scanner.indicators.patterns import flag_hits
from scanner.indicators.ranging import range_state
from scanner.indicators.swings import Leg, Swing, last_leg, last_swing, zigzag
from scanner.indicators.thrust import hook_reversal_hits, thrust_hits
from scanner.indicators.trend import trend_state
from scanner.indicators.trendlines import trendline_hits
from tests.barkit import bars, mirror, zigzag_path

PIP = 0.0001


def dirs(hits: list[Hit]) -> set[str]:
    return {h.direction for h in hits}


# Touch helpers


def test_bar_touch_edges() -> None:
    assert bar_touches(1.1010, 1.1000, 1.0990, 10 * PIP)  # exactly 10 pips below the low
    assert not bar_touches(1.1010, 1.1000, 1.09899, 10 * PIP)
    assert bar_touches(1.1010, 1.1000, 1.1005, 0)  # inside the bar


def test_direction_for_level() -> None:
    assert direction_for_level(1.0, 1.1) == "long"
    assert direction_for_level(1.2, 1.1) == "short"
    assert direction_for_level(1.1, 1.1) == "either"


def test_level_hit_reports_distance_from_close() -> None:
    b = bars([(1.08440, 1.08460, 1.08355, 1.08420)])
    hit = level_hit(b, 0, 1.08360, "daily.S1", 10, PIP)
    assert hit is not None
    assert hit.direction == "long"
    assert hit.distance_pips == 6.0


# Swings and trend


def test_zigzag_confirms_swings_only_after_threshold() -> None:
    b = zigzag_path([1.1000, 1.1030, 1.1010, 1.1040], step=0.0005)
    swings = zigzag(b, 20 * PIP)
    assert [(s.kind, round(s.price, 4)) for s in swings] == [
        ("low", 1.1000), ("high", 1.1030), ("low", 1.1010),
    ]  # fmt: skip
    for s in swings:
        assert s.confirmed_index > s.index


def test_zigzag_has_no_look_ahead() -> None:
    b = zigzag_path([1.1000, 1.1030, 1.1015], step=0.0005)
    # The 15-pip pullback has not reached the 20-pip threshold: the high is not a swing yet.
    assert [s.kind for s in zigzag(b, 20 * PIP)] == ["low"]
    assert [s.kind for s in zigzag(b, 10 * PIP)] == ["low", "high"]


def test_trend_states() -> None:
    up = zigzag(zigzag_path([1.10, 1.1030, 1.1010, 1.1050, 1.1030, 1.1070]), 15 * PIP)
    assert trend_state(up) == "up"
    down = zigzag(zigzag_path([1.11, 1.1070, 1.1090, 1.1050, 1.1070, 1.1030]), 15 * PIP)
    assert trend_state(down) == "down"
    lower_both = zigzag(zigzag_path([1.10, 1.1050, 1.1010, 1.1040, 1.1000, 1.1030]), 15 * PIP)
    assert trend_state(lower_both) == "down"
    mixed = zigzag(zigzag_path([1.10, 1.1040, 1.1010, 1.1060, 1.1000, 1.1030]), 15 * PIP)
    assert trend_state(mixed) == "none"  # higher high, lower low
    assert trend_state([]) == "none"


def test_last_leg_and_last_swing() -> None:
    swings = [Swing("low", 0, 1.081, 3), Swing("high", 5, 1.089, 8)]
    leg = last_leg(swings)
    assert leg is not None and leg.up and round(leg.size, 5) == 0.008
    assert last_swing(swings, "low") == swings[0]
    assert last_leg(swings[:1]) is None


# Fibonacci


LEG = Leg(Swing("low", 0, 1.08100, 2), Swing("high", 10, 1.08900, 12))


def test_retracement_levels() -> None:
    lv = retracements(LEG, "fib")
    assert lv["fib.61.8"] == pytest.approx(1.084056)
    assert lv["fib.50.0"] == pytest.approx(1.085)
    assert set(retracements(LEG, "thirds")) == {"fib.33.3", "fib.50.0", "fib.66.7"}


def test_fibonacci_fires_long_on_up_leg_retracement() -> None:
    b = bars([(1.08440, 1.08445, 1.08380, 1.08420)])
    hits = fibonacci_hits(b, 0, LEG, 5, "fib", PIP)
    assert [h.level_ref for h in hits] == ["fib.61.8"]
    assert hits[0].direction == "long"
    assert hits[0].detail["leg"] == [1.081, 1.089]


def test_fibonacci_edge_of_tolerance_and_short_side() -> None:
    level = 1.084056
    at_edge = bars([(level + 0.0007, level + 0.0008, level + 0.0005, level + 0.0006)])
    assert fibonacci_hits(at_edge, 0, LEG, 5, "fib", PIP)
    beyond = bars([(level + 0.0007, level + 0.0008, level + 0.00051, level + 0.0006)])
    assert not [
        h for h in fibonacci_hits(beyond, 0, LEG, 5, "fib", PIP) if h.level_ref == "fib.61.8"
    ]
    below = bars([(level - 0.0005, level - 0.0001, level - 0.0007, level - 0.0003)])
    assert dirs(fibonacci_hits(below, 0, LEG, 5, "fib", PIP)) == {"short"}
    assert fibonacci_hits(at_edge, 0, None, 5, "fib", PIP) == []


# Pivots and previous day


PIVOTS = {
    "daily": {"P": 1.0894, "R1": 1.0910, "S1": 1.0836, "S2": 1.0820, "R2": 1.0968},
    "weekly": {"P": 1.0830, "S1": 1.0700},
}
TOLS = {"daily": 10, "weekly": 15, "monthly": 15}


def test_pivot_touch_daily_and_double_pivot() -> None:
    b = bars([(1.0844, 1.0846, 1.0838, 1.0842)])
    hits = pivot_hits(b, 0, PIVOTS, TOLS, 10, PIP)
    refs = {h.level_ref: h for h in hits}
    assert set(refs) == {"daily.S1", "weekly.P"}
    assert refs["daily.S1"].direction == "long"
    assert refs["daily.S1"].detail["double_pivot"] == "weekly.P"


def test_pivot_tolerance_per_set() -> None:
    b = bars([(1.0716, 1.0718, 1.0715, 1.0716)])  # 15 pips above weekly S1
    assert [h.level_ref for h in pivot_hits(b, 0, PIVOTS, TOLS, 10, PIP)] == ["weekly.S1"]
    tight = {**TOLS, "weekly": 14}
    assert pivot_hits(b, 0, PIVOTS, tight, 10, PIP) == []


def test_pivot_resistance_is_short() -> None:
    b = bars([(1.0900, 1.0905, 1.0898, 1.0902)])
    hits = pivot_hits(b, 0, PIVOTS, TOLS, 10, PIP)
    assert {h.level_ref: h.direction for h in hits}["daily.R1"] == "short"


def test_prev_day_high_and_low() -> None:
    b = bars([(1.0900, 1.0906, 1.0895, 1.0898)])
    assert dirs(prev_day_hit(b, 0, 1.0905, "pdh", 10, PIP)) == {"short"}
    assert prev_day_hit(b, 0, 1.0920, "pdh", 10, PIP) == []
    assert prev_day_hit(b, 0, None, "pdl", 10, PIP) == []
    assert dirs(prev_day_hit(b, 0, 1.0890, "pdl", 10, PIP)) == {"long"}


# Candlesticks


def _calm(n: int, base: float = 1.1000) -> list[tuple[float, float, float, float]]:
    return [
        (base, base + 0.0004, base - 0.0004, base + (0.0002 if k % 2 else -0.0002))
        for k in range(n)
    ]


def test_bullish_engulfing() -> None:
    rows = [*_calm(30), (1.101, 1.1012, 1.0995, 1.0998), (1.0994, 1.1018, 1.0992, 1.1015)]
    hits = candlestick_hits(bars(rows), len(rows) - 1, ["CDLENGULFING"], 2, 5)
    assert any(h.detail["pattern"] == "Engulfing (bullish)" and h.direction == "long" for h in hits)


def test_bearish_engulfing_and_lookback() -> None:
    rows = [*_calm(30), (1.0995, 1.1012, 1.0994, 1.101), (1.1014, 1.1016, 1.099, 1.0992)]
    b = bars(rows)
    hits = candlestick_hits(b, len(rows) - 1, ["CDLENGULFING"], 2, 5)
    assert any(h.direction == "short" for h in hits)
    later = bars([*rows, *_calm(3, 1.0992)])
    old = [
        h
        for h in candlestick_hits(later, len(later) - 1, ["CDLENGULFING"], 2, 5)
        if h.detail["bars_ago"] >= 2
    ]
    assert old == []


def test_doji_is_direction_neutral() -> None:
    rows = [*_calm(30), (1.1, 1.1015, 1.0985, 1.1)]
    hits = candlestick_hits(bars(rows), len(rows) - 1, ["CDLDOJI"], 1, 5)
    assert hits and all(h.direction == "either" for h in hits)


def test_shaved_bars() -> None:
    rows = [(1.1000, 1.1020, 1.0990, 1.1019)]  # upper shadow 1 of 30 points: 3.3 percent
    hits = candlestick_hits(bars(rows), 0, ["SHAVED"], 1, 5)
    assert [h.detail["pattern"] for h in hits] == ["Shaved head (bullish)"]
    assert candlestick_hits(bars(rows), 0, ["SHAVED"], 1, 3) == []
    bear = [(1.1020, 1.1030, 1.1000, 1.1001)]
    assert dirs(candlestick_hits(bars(bear), 0, ["SHAVED"], 1, 5)) == {"short"}


# New high/low failure


def test_hl_failure_short_at_swing_high() -> None:
    swings = [Swing("low", 0, 1.0800, 2), Swing("high", 5, 1.0900, 8)]
    b = bars([(1.0880, 1.0896, 1.0878, 1.0885)])  # 4 pips short of the high, closes below
    assert dirs(hl_failure_hits(b, 0, swings, 5, PIP)) == {"short"}
    above = bars([(1.0880, 1.0902, 1.0878, 1.0901)])  # closes beyond: no failure
    assert hl_failure_hits(above, 0, swings, 5, PIP) == []
    short_of = bars([(1.0880, 1.08949, 1.0878, 1.0885)])  # 5.1 pips away
    assert hl_failure_hits(short_of, 0, swings, 5, PIP) == []


def test_hl_failure_long_at_swing_low() -> None:
    swings = [Swing("high", 0, 1.0900, 2), Swing("low", 5, 1.0800, 8)]
    b = bars([(1.0810, 1.0812, 1.0795, 1.0805)])  # pierces and closes back above
    assert dirs(hl_failure_hits(b, 0, swings, 5, PIP)) == {"long"}


# Thrust candle and hook reversal


def test_thrust_candle() -> None:
    assert dirs(thrust_hits(bars([(1.1000, 1.1016, 1.0999, 1.1015)]), 0, 15, PIP)) == {"long"}
    assert dirs(thrust_hits(bars([(1.1015, 1.1016, 1.0999, 1.1000)]), 0, 15, PIP)) == {"short"}
    assert thrust_hits(bars([(1.1000, 1.1016, 1.0999, 1.10149)]), 0, 15, PIP) == []


def test_hook_reversal_after_long_leg() -> None:
    rows = [(1.1000 + k * 0.0010, 1.1000 + (k + 1) * 0.0010, 1.1000 + k * 0.0010 - 0.0001,
             1.1000 + (k + 1) * 0.0010) for k in range(7)]  # fmt: skip
    rows.append((1.1075, 1.1076, 1.1060, 1.1065))  # opens above prior high, closes inside
    swings = [Swing("low", 0, 1.0999, 2)]
    assert dirs(hook_reversal_hits(bars(rows), len(rows) - 1, swings, 60, PIP)) == {"short"}
    assert hook_reversal_hits(bars(rows), len(rows) - 1, swings, 80, PIP) == []


# Range detection


def test_range_detected_after_retests() -> None:
    rows = []
    for k in range(32):
        top = k % 8 == 0
        bottom = k % 8 == 4
        h = 1.1025 if top else 1.1015
        low = 1.1000 if bottom else 1.1008
        rows.append((1.1012, h, low, 1.1012))
    state = range_state(bars(rows), 31, 32, 2, 5, 20, PIP)
    assert state.ranging
    assert state.retests_high >= 2 and state.width_pips == 25.0
    narrow = range_state(bars(rows), 31, 32, 2, 5, 30, PIP)
    assert not narrow.ranging
    short_window = range_state(bars(rows[:20]), 19, 32, 2, 5, 20, PIP)
    assert not short_window.ranging


# Flags and trendlines


def test_bull_flag_breakout() -> None:
    rows = [(1.1000 + k * 0.0008, 1.1000 + (k + 1) * 0.0008, 1.1000 + k * 0.0008 - 0.0001,
             1.1000 + (k + 1) * 0.0008) for k in range(5)]  # fmt: skip
    top = 1.1040
    for k in range(6):  # drifting consolidation below the pole high
        hi = top - 0.0002 - k * 0.0001
        rows.append((hi - 0.0004, hi, hi - 0.0008, hi - 0.0004))
    rows.append((1.1032, 1.1048, 1.1031, 1.1046))  # breakout close
    hits = flag_hits(bars(rows), len(rows) - 1, 30, 6, 4, 20, PIP)
    assert dirs(hits) == {"long"}
    assert hits[0].detail["pole_pips"] >= 30
    assert flag_hits(bars(rows), len(rows) - 1, 60, 6, 4, 20, PIP) == []
    bear = mirror(bars(rows))
    assert dirs(flag_hits(bear, len(rows) - 1, 30, 6, 4, 20, PIP)) == {"short"}


def test_trendline_support_touch() -> None:
    # Three rising swing lows on one line, then price comes back to it.
    points = [1.1000, 1.1030, 1.1010, 1.1040, 1.1020, 1.1050, 1.1030]
    b = zigzag_path(points, step=0.0005)
    swings = zigzag(b, 15 * PIP)
    lows = [s for s in swings if s.kind == "low"]
    assert len(lows) >= 3
    hits = trendline_hits(b, len(b) - 1, swings, 3, 3, 15, 480, PIP)
    assert any(h.detail["side"] == "support" and h.supports("long") for h in hits)
    assert trendline_hits(b, len(b) - 1, swings, 4, 3, 15, 480, PIP) == []
    down = mirror(b)
    hits = trendline_hits(down, len(down) - 1, zigzag(down, 15 * PIP), 3, 3, 15, 480, PIP)
    assert any(h.detail["side"] == "resistance" and h.supports("short") for h in hits)


def test_trendline_breaks_on_close_beyond() -> None:
    points = [1.1000, 1.1030, 1.1010, 1.1040, 1.1020, 1.1050, 1.1030]
    b = zigzag_path(points, step=0.0005)
    rows = list(zip(b.o, b.h, b.l, b.c, strict=True))
    rows.append((1.1030, 1.1031, 1.0990, 1.0995))  # closes well below the support line
    rows.append((1.0995, 1.1000, 1.0990, 1.0998))
    broken = bars(rows)
    hits = trendline_hits(broken, len(rows) - 1, zigzag(broken, 15 * PIP), 3, 3, 15, 480, PIP)
    assert not any(h.detail["side"] == "support" for h in hits)


def test_arrays_are_float64() -> None:
    assert bars([(1.0, 1.0, 1.0, 1.0)]).c.dtype == np.float64
