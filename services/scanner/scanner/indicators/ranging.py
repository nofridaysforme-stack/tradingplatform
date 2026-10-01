"""Range detection (three_eight.range_detect).

Ranging when, over the last lookback_bars, price retested the same high or low at least
min_retests times within the tolerance, and the range is at least min_width_pips wide.
A retest is a separate visit: consecutive touching bars count once, and the first visit
that set the extreme is not a retest.
"""

from dataclasses import dataclass

import numpy as np

from scanner.indicators.base import Bars, FloatArray, pips


@dataclass(frozen=True)
class RangeState:
    ranging: bool
    high: float
    low: float
    width_pips: float
    retests_high: int
    retests_low: int


def _visits(touching: np.ndarray) -> int:
    count, prev = 0, False
    for t in touching:
        if t and not prev:
            count += 1
        prev = bool(t)
    return count


def range_state(
    bars: Bars,
    i: int,
    lookback_bars: int,
    min_retests: int,
    retest_tolerance_pips: float,
    min_width_pips: float,
    pip_size: float,
) -> RangeState:
    start = max(0, i - lookback_bars + 1)
    hs: FloatArray = bars.h[start : i + 1]
    ls: FloatArray = bars.l[start : i + 1]
    high, low = float(hs.max()), float(ls.min())
    tol = retest_tolerance_pips * pip_size + 1e-9
    retests_high = max(0, _visits(hs >= high - tol) - 1)
    retests_low = max(0, _visits(ls <= low + tol) - 1)
    width = pips(high - low, pip_size)
    full = i - start + 1 >= lookback_bars
    ranging = (
        full and max(retests_high, retests_low) >= min_retests and width + 1e-9 >= min_width_pips
    )
    return RangeState(ranging, high, low, round(width, 1), retests_high, retests_low)
