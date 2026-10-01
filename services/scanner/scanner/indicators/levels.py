"""Price-level indicators: pivot touch (three_eight.pivot_touch) and previous day high and
low (three_eight.pdh, three_eight.pdl)."""

from collections.abc import Mapping

from scanner.indicators.base import Bars, Hit, level_hit

PIVOT_NAMES = ("P", "R1", "R2", "R3", "S1", "S2", "S3")
PIVOT_SETS = ("daily", "weekly", "monthly")


def pivot_hits(
    bars: Bars,
    i: int,
    pivots: Mapping[str, Mapping[str, float]],
    tolerances_pips: Mapping[str, float],
    double_pivot_pips: float,
    pip_size: float,
) -> list[Hit]:
    """pivots: {"daily": {"P": ..., "R1": ...}, "weekly": {...}, "monthly": {...}}."""
    hits: list[Hit] = []
    for set_name in PIVOT_SETS:
        levels = pivots.get(set_name)
        if not levels:
            continue
        for name in PIVOT_NAMES:
            if name not in levels:
                continue
            level = float(levels[name])
            hit = level_hit(
                bars, i, level, f"{set_name}.{name}", tolerances_pips[set_name], pip_size
            )
            if hit is None:
                continue
            detail: dict[str, object] = {"level": level, "distance_pips": hit.distance_pips}
            partner = _double_pivot(set_name, level, pivots, double_pivot_pips * pip_size)
            if partner:
                detail["double_pivot"] = partner
            hits.append(Hit(hit.direction, hit.level_ref, level, hit.distance_pips, detail))
    return hits


def _double_pivot(
    set_name: str, level: float, pivots: Mapping[str, Mapping[str, float]], gap: float
) -> str | None:
    """A daily level within gap of a weekly or monthly level (or the reverse) is a double pivot."""
    others = ("weekly", "monthly") if set_name == "daily" else ("daily",)
    for other in others:
        for name, value in (pivots.get(other) or {}).items():
            if name in PIVOT_NAMES and abs(float(value) - level) <= gap + 1e-9:
                return f"{other}.{name}"
    return None


def prev_day_hit(
    bars: Bars, i: int, level: float | None, ref: str, tolerance_pips: float, pip_size: float
) -> list[Hit]:
    if level is None:
        return []
    hit = level_hit(bars, i, level, ref, tolerance_pips, pip_size)
    if hit is None:
        return []
    return [Hit(hit.direction, ref, level, hit.distance_pips, {"level": level})]
