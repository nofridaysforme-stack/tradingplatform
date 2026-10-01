"""ZigZag swings (rule three_eight.swing).

A swing high is confirmed once price falls threshold below the highest high since the last
swing low (and the mirror for lows). Each swing records the bar that confirmed it, so a
swing is never used before it would have been known live (no look-ahead).
"""

from dataclasses import dataclass
from typing import Literal

from scanner.indicators.base import Bars


@dataclass(frozen=True)
class Swing:
    kind: Literal["high", "low"]
    index: int  # bar where the extreme printed
    price: float
    confirmed_index: int  # bar whose move confirmed it


def zigzag(bars: Bars, threshold: float) -> list[Swing]:
    """Confirmed swings for bars, oldest first. threshold is a price distance."""
    n = len(bars)
    if n == 0:
        return []
    swings: list[Swing] = []
    direction = 0  # 1 up (tracking a high), -1 down (tracking a low), 0 unknown
    hi, hi_i = float(bars.h[0]), 0
    lo, lo_i = float(bars.l[0]), 0
    for i in range(1, n):
        h, low = float(bars.h[i]), float(bars.l[i])
        if direction >= 0 and h > hi:
            hi, hi_i = h, i
        if direction <= 0 and low < lo:
            lo, lo_i = low, i
        if direction == 0:
            if h - lo >= threshold and lo_i < i:
                swings.append(Swing("low", lo_i, lo, i))
                direction, hi, hi_i = 1, h, i
            elif hi - low >= threshold and hi_i < i:
                swings.append(Swing("high", hi_i, hi, i))
                direction, lo, lo_i = -1, low, i
        elif direction == 1 and hi - low >= threshold and hi_i < i:
            swings.append(Swing("high", hi_i, hi, i))
            direction, lo, lo_i = -1, low, i
        elif direction == -1 and h - lo >= threshold and lo_i < i:
            swings.append(Swing("low", lo_i, lo, i))
            direction, hi, hi_i = 1, h, i
    return swings


@dataclass(frozen=True)
class Leg:
    start: Swing
    end: Swing

    @property
    def up(self) -> bool:
        return self.end.price > self.start.price

    @property
    def size(self) -> float:
        return abs(self.end.price - self.start.price)


def last_leg(swings: list[Swing]) -> Leg | None:
    """The most recent completed swing-to-swing move."""
    if len(swings) < 2:
        return None
    return Leg(swings[-2], swings[-1])


def last_swing(swings: list[Swing], kind: Literal["high", "low"]) -> Swing | None:
    for s in reversed(swings):
        if s.kind == kind:
            return s
    return None
