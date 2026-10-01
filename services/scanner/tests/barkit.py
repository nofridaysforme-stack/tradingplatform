"""Build hand-made bar sequences for tests."""

import itertools
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from scanner.indicators.base import Bars

START = datetime(2026, 10, 5, 4, 0, tzinfo=UTC)  # Monday 00:00 New York


def bars(ohlc: Sequence[tuple[float, float, float, float]], start: datetime = START) -> Bars:
    rows = [(start + timedelta(minutes=15 * k), *row) for k, row in enumerate(ohlc)]
    return Bars.from_rows(rows)


def path(closes: Sequence[float], wick: float = 0.0001) -> Bars:
    """Bars that open at the previous close and move to each close, with small wicks."""
    rows = []
    prev = closes[0]
    for c in closes:
        o = prev
        rows.append((o, max(o, c) + wick, min(o, c) - wick, c))
        prev = c
    return bars(rows)


def zigzag_path(points: Sequence[float], step: float = 0.0005, wick: float = 0.0) -> Bars:
    """Walk straight lines between turning points in equal steps."""
    closes = [points[0]]
    for a, b in itertools.pairwise(points):
        n = max(1, round(abs(b - a) / step))
        closes.extend(a + (b - a) * k / n for k in range(1, n + 1))
    return path(closes, wick)


def mirror(b: Bars, axis: float = 2.2) -> Bars:
    """Reflect prices around axis: an up move becomes a down move; highs and lows swap."""
    return Bars(b.ts, axis - b.o, axis - b.l, axis - b.h, axis - b.c)
