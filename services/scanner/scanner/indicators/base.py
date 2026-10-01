"""Shared types for indicators. Prices are float64 for speed over long histories; pip
distances are compared with a small epsilon so a value exactly at a tolerance counts."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

Direction = Literal["long", "short"]
HitDirection = Literal["long", "short", "either"]
FloatArray = npt.NDArray[np.float64]
EPS = 1e-9


@dataclass(frozen=True)
class Bars:
    """Completed bars, oldest first. ts is each bar's open time (UTC)."""

    ts: Sequence[datetime]
    o: FloatArray
    h: FloatArray
    l: FloatArray  # noqa: E741
    c: FloatArray

    def __len__(self) -> int:
        return len(self.ts)

    @classmethod
    def from_rows(cls, rows: Sequence[tuple[datetime, float, float, float, float]]) -> "Bars":
        return cls(
            ts=[r[0] for r in rows],
            o=np.array([r[1] for r in rows], dtype=np.float64),
            h=np.array([r[2] for r in rows], dtype=np.float64),
            l=np.array([r[3] for r in rows], dtype=np.float64),
            c=np.array([r[4] for r in rows], dtype=np.float64),
        )

    def upto(self, i: int) -> "Bars":
        """Bars 0..i inclusive: what was known when bar i completed."""
        end = i + 1
        return Bars(self.ts[:end], self.o[:end], self.h[:end], self.l[:end], self.c[:end])


@dataclass(frozen=True)
class Hit:
    """One reason an indicator fired, in one direction."""

    direction: HitDirection
    level_ref: str | None = None
    level: float | None = None
    distance_pips: float | None = None  # from the bar close, for display
    detail: dict[str, Any] = field(default_factory=dict)

    def supports(self, direction: Direction) -> bool:
        return self.direction in (direction, "either")


def pips(distance: float, pip_size: float) -> float:
    return distance / pip_size


def within(value_pips: float, tolerance_pips: float) -> bool:
    return value_pips <= tolerance_pips + EPS


def bar_touches(high: float, low: float, level: float, tolerance: float) -> bool:
    """Any part of the bar (high to low) lies within tolerance of the level (decision A22)."""
    return low - tolerance - EPS <= level <= high + tolerance + EPS


def direction_for_level(level: float, close: float) -> HitDirection:
    """Support at or below the close means long; resistance at or above means short."""
    if abs(level - close) <= EPS:
        return "either"
    return "long" if level < close else "short"


def level_hit(
    bars: Bars, i: int, level: float, ref: str, tolerance_pips: float, pip_size: float
) -> Hit | None:
    if not bar_touches(bars.h[i], bars.l[i], level, tolerance_pips * pip_size):
        return None
    close = float(bars.c[i])
    return Hit(
        direction=direction_for_level(level, close),
        level_ref=ref,
        level=level,
        distance_pips=round(pips(abs(close - level), pip_size), 1),
    )
