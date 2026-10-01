"""Flags, pennants, triangles (three_eight.flag_pennant_triangle). Provisional.

Pole: a move of at least pole_min_pips within pole_max_bars. Consolidation: cons_min_bars to
cons_max_bars bars after the pole whose highs and lows fit parallel (flag) or converging
(pennant, triangle) regression lines, staying within the pole and retracing at most half
of it. Fires when the signal bar closes beyond the consolidation in the pole's direction.
Projected target: the pole length from the breakout close.
"""

import numpy as np

from scanner.indicators.base import Bars, FloatArray, Hit, pips

MAX_RETRACE = 0.5  # consolidation may give back at most half the pole
PARALLEL_SLACK = 0.25  # slopes within 25 percent of each other read as parallel


def _fit(y: FloatArray) -> tuple[float, float]:
    x = np.arange(len(y), dtype=np.float64)
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def _shape(slope_hi: float, slope_lo: float, scale: float) -> str | None:
    if abs(slope_hi - slope_lo) <= PARALLEL_SLACK * max(abs(slope_hi), abs(slope_lo), scale):
        return "flag"
    if slope_hi < slope_lo:
        return "pennant"
    return None  # diverging


def flag_hits(
    bars: Bars,
    i: int,
    pole_min_pips: float,
    pole_max_bars: int,
    cons_min_bars: int,
    cons_max_bars: int,
    pip_size: float,
) -> list[Hit]:
    close = float(bars.c[i])
    for n in range(cons_min_bars, cons_max_bars + 1):
        pole_end = i - n - 1
        if pole_end < 1:
            break
        cons_h: FloatArray = bars.h[i - n : i]
        cons_l: FloatArray = bars.l[i - n : i]
        p_start = max(0, pole_end - pole_max_bars + 1)  # the pole may be shorter
        slope_hi, icpt_hi = _fit(cons_h)
        slope_lo, icpt_lo = _fit(cons_l)
        shape = _shape(slope_hi, slope_lo, pip_size / 10)
        if shape is None:
            continue
        upper = icpt_hi + slope_hi * n
        lower = icpt_lo + slope_lo * n

        pole_high = float(bars.h[pole_end])
        pole_low = float(bars.l[p_start : pole_end + 1].min())
        move = pole_high - pole_low
        if (
            pips(move, pip_size) + 1e-9 >= pole_min_pips
            and pole_high >= float(bars.h[p_start : pole_end + 1].max())
            and float(cons_h.max()) <= pole_high
            and float(cons_l.min()) >= pole_high - MAX_RETRACE * move
            and close > upper
        ):
            return [_hit("long", shape, move, n, close + move, pip_size)]

        pole_low = float(bars.l[pole_end])
        pole_high = float(bars.h[p_start : pole_end + 1].max())
        move = pole_high - pole_low
        if (
            pips(move, pip_size) + 1e-9 >= pole_min_pips
            and pole_low <= float(bars.l[p_start : pole_end + 1].min())
            and float(cons_l.min()) >= pole_low
            and float(cons_h.max()) <= pole_low + MAX_RETRACE * move
            and close < lower
        ):
            return [_hit("short", shape, move, n, close - move, pip_size)]
    return []


def _hit(direction: str, shape: str, move: float, n: int, target: float, pip_size: float) -> Hit:
    label = {"flag": "Flag", "pennant": "Pennant or triangle"}[shape]
    side = "bullish" if direction == "long" else "bearish"
    return Hit(
        direction,  # type: ignore[arg-type]
        "pattern",
        detail={
            "pattern": f"{label} ({side})",
            "pole_pips": round(pips(move, pip_size), 1),
            "consolidation_bars": n,
            "projected_target": target,
        },
    )
