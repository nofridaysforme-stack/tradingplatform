"""Broker adjustment (spec 10). Signals are computed on mid prices; each owner's view shifts
the levels by half their broker's typical spread.

long:  entry + half, stop - half, target - half
short: entry - half, stop + half, target + half
"""

from dataclasses import dataclass

from scanner.indicators.base import Direction


@dataclass(frozen=True)
class Adjusted:
    entry: float
    stop: float
    target: float
    reward_risk: float


def adjust(
    direction: Direction,
    entry: float,
    stop: float,
    target: float,
    typical_spread_pips: float,
    pip_size: float,
    decimals: int = 5,
) -> Adjusted:
    half = typical_spread_pips / 2 * pip_size
    if direction == "long":
        e, s, t = entry + half, stop - half, target - half
    else:
        e, s, t = entry - half, stop + half, target + half
    risk = abs(e - s)
    ratio = abs(t - e) / risk if risk else 0.0
    return Adjusted(round(e, decimals), round(s, decimals), round(t, decimals), round(ratio, 3))
