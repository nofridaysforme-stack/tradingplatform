"""Fibonacci retracements of the last leg (indicator three_eight.fibonacci)."""

from scanner.indicators.base import Bars, Hit, level_hit
from scanner.indicators.swings import Leg

RATIO_SETS = {
    "fib": (0.382, 0.5, 0.618),
    "thirds": (1 / 3, 0.5, 2 / 3),
}


def ratio_ref(ratio: float) -> str:
    return f"fib.{ratio * 100:.1f}"


def retracements(leg: Leg, ratio_set: str) -> dict[str, float]:
    """Levels measured back from the end of the leg toward its start."""
    span = leg.end.price - leg.start.price
    return {ratio_ref(r): leg.end.price - r * span for r in RATIO_SETS[ratio_set]}


def fibonacci_hits(
    bars: Bars, i: int, leg: Leg | None, tolerance_pips: float, ratio_set: str, pip_size: float
) -> list[Hit]:
    if leg is None:
        return []
    hits: list[Hit] = []
    for ref, level in retracements(leg, ratio_set).items():
        hit = level_hit(bars, i, level, ref, tolerance_pips, pip_size)
        if hit is not None:
            hits.append(
                Hit(
                    hit.direction,
                    hit.level_ref,
                    hit.level,
                    hit.distance_pips,
                    {"leg": [leg.start.price, leg.end.price]},
                )
            )
    return hits
