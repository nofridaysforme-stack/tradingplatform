"""Candlestick formations (three_eight.candlestick), using TA-Lib plus shaved bars.

A pattern counts when it completes on the signal bar or up to lookback_bars - 1 bars before.
TA-Lib returns a positive value for bullish and negative for bearish patterns. Doji and
spinning top are direction-neutral and count in the trigger's direction.
"""

from collections.abc import Sequence

import numpy as np
import talib

from scanner.indicators.base import Bars, Hit

NAMES = {
    "CDLDOJI": "Doji",
    "CDLHAMMER": "Hammer",
    "CDLINVERTEDHAMMER": "Inverted hammer",
    "CDLHARAMICROSS": "Harami cross",
    "CDLHANGINGMAN": "Hanging man",
    "CDLDARKCLOUDCOVER": "Dark cloud cover",
    "CDLPIERCING": "Piercing",
    "CDLSPINNINGTOP": "Spinning top",
    "CDLENGULFING": "Engulfing",
}
NEUTRAL = {"CDLDOJI", "CDLSPINNINGTOP"}
# TA-Lib averages earlier candle bodies and shadows; give it this much history.
WARMUP = 30


def candlestick_hits(
    bars: Bars,
    i: int,
    patterns: Sequence[str],
    lookback_bars: int,
    shaved_max_shadow_pct: float,
) -> list[Hit]:
    start = max(0, i - WARMUP - lookback_bars)
    o, h, l, c = (np.ascontiguousarray(a[start : i + 1]) for a in (bars.o, bars.h, bars.l, bars.c))  # noqa: E741
    last = len(c) - 1
    window = range(max(0, last - lookback_bars + 1), last + 1)
    hits: list[Hit] = []
    for code in patterns:
        if code == "SHAVED":
            continue
        out = getattr(talib, code)(o, h, l, c)
        for j in window:
            value = int(out[j])
            if value == 0:
                continue
            if code in NEUTRAL:
                direction, label = "either", NAMES[code]
            else:
                bullish = value > 0
                direction = "long" if bullish else "short"
                label = f"{NAMES[code]} ({'bullish' if bullish else 'bearish'})"
            hits.append(Hit(direction, detail={"pattern": label, "bars_ago": last - j}))  # type: ignore[arg-type]
    if "SHAVED" in patterns:
        for j in window:
            hit = _shaved(o[j], h[j], l[j], c[j], shaved_max_shadow_pct, last - j)
            if hit is not None:
                hits.append(hit)
    return hits


def _shaved(o: float, h: float, l: float, c: float, max_pct: float, bars_ago: int) -> Hit | None:  # noqa: E741
    """Shaved head: a bullish bar with almost no upper shadow. Shaved bottom: a bearish bar
    with almost no lower shadow. Shadow at most max_pct of the bar's range."""
    rng = h - l
    if rng <= 0:
        return None
    limit = rng * max_pct / 100 + 1e-12
    if c > o and h - c <= limit:
        return Hit("long", detail={"pattern": "Shaved head (bullish)", "bars_ago": bars_ago})
    if c < o and c - l <= limit:
        return Hit("short", detail={"pattern": "Shaved bottom (bearish)", "bars_ago": bars_ago})
    return None
