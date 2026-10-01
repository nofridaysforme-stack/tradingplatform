"""New high/low failure (three_eight.hl_failure).

Shorts: price tests the high of the most recent up leg within the tolerance and the bar
closes without exceeding it. Longs: the mirror at the low of the most recent down leg.
"""

from scanner.indicators.base import Bars, Hit, pips
from scanner.indicators.swings import Swing, last_swing


def hl_failure_hits(
    bars: Bars, i: int, swings: list[Swing], tolerance_pips: float, pip_size: float
) -> list[Hit]:
    tol = tolerance_pips * pip_size + 1e-9
    h, low, c = float(bars.h[i]), float(bars.l[i]), float(bars.c[i])
    hits: list[Hit] = []
    top = last_swing(swings, "high")
    if top is not None and h >= top.price - tol and c <= top.price:
        hits.append(
            Hit("short", "swing.high", top.price, round(pips(top.price - c, pip_size), 1),
                {"tested": top.price, "bar_high": h})
        )  # fmt: skip
    bottom = last_swing(swings, "low")
    if bottom is not None and low <= bottom.price + tol and c >= bottom.price:
        hits.append(
            Hit("long", "swing.low", bottom.price, round(pips(c - bottom.price, pip_size), 1),
                {"tested": bottom.price, "bar_low": low})
        )  # fmt: skip
    return hits
