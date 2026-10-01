"""Trendlines and channels (three_eight.trendline_channel). Provisional.

A trendline joins swing lows (support) or swing highs (resistance) and has at least
min_touches swing points within touch_tolerance_pips of it. It stops being valid on the
first close beyond it by more than the tolerance, or when its first touch is older than
max_line_age_bars. Fires when the signal bar touches a valid line. A channel exists when a
valid line on the opposite swings has a slope within parallel_tolerance_pct.
"""

from dataclasses import dataclass
from itertools import combinations

from scanner.indicators.base import Bars, Hit, bar_touches, direction_for_level, pips
from scanner.indicators.swings import Swing

MAX_SWINGS_PER_SIDE = 8  # newest swing points considered per side


@dataclass(frozen=True)
class Line:
    side: str  # "support" or "resistance"
    start: int
    slope: float
    intercept: float  # value at start
    touches: int

    def at(self, index: int) -> float:
        return self.intercept + self.slope * (index - self.start)


def _lines(
    bars: Bars, i: int, points: list[Swing], side: str, tol: float, min_touches: int
) -> list[Line]:
    lines: list[Line] = []
    for a, b in combinations(points, 2):
        slope = (b.price - a.price) / (b.index - a.index)
        line = Line(side, a.index, slope, a.price, 0)
        touches = sum(
            1 for p in points if p.index >= a.index and abs(line.at(p.index) - p.price) <= tol
        )
        if touches < min_touches:
            continue
        closes = bars.c[a.index : i]
        values = [line.at(k) for k in range(a.index, i)]
        broken = any(
            (c < v - tol) if side == "support" else (c > v + tol)
            for c, v in zip(closes, values, strict=True)
        )
        if not broken:
            lines.append(Line(side, a.index, slope, a.price, touches))
    return lines


def trendline_hits(
    bars: Bars,
    i: int,
    swings: list[Swing],
    min_touches: int,
    touch_tolerance_pips: float,
    parallel_tolerance_pct: float,
    max_line_age_bars: int,
    pip_size: float,
) -> list[Hit]:
    tol = touch_tolerance_pips * pip_size + 1e-9
    oldest = i - max_line_age_bars
    lows = [s for s in swings if s.kind == "low" and s.index >= oldest][-MAX_SWINGS_PER_SIDE:]
    highs = [s for s in swings if s.kind == "high" and s.index >= oldest][-MAX_SWINGS_PER_SIDE:]
    support = _lines(bars, i, lows, "support", tol, min_touches)
    resistance = _lines(bars, i, highs, "resistance", tol, min_touches)

    hits: list[Hit] = []
    close = float(bars.c[i])
    for line, opposite in ((support, resistance), (resistance, support)):
        touched = [ln for ln in line if bar_touches(bars.h[i], bars.l[i], ln.at(i), tol)]
        if not touched:
            continue
        best = max(touched, key=lambda ln: (ln.touches, ln.start))
        level = best.at(i)
        channel = any(_parallel(best.slope, o.slope, parallel_tolerance_pct) for o in opposite)
        hits.append(
            Hit(
                direction_for_level(level, close),
                f"trendline.{best.side}",
                level,
                round(pips(abs(close - level), pip_size), 1),
                {"side": best.side, "touches": best.touches, "channel": channel},
            )
        )
    return hits


def _parallel(a: float, b: float, pct: float) -> bool:
    scale = max(abs(a), abs(b))
    if scale == 0:
        return True
    return abs(a - b) <= scale * pct / 100
