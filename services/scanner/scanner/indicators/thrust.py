"""Thrust candle (three_eight.thrust_candle) and hook reversal (three_eight.hook_reversal)."""

from scanner.indicators.base import Bars, Hit, pips
from scanner.indicators.swings import Swing


def thrust_hits(bars: Bars, i: int, min_body_pips: float, pip_size: float) -> list[Hit]:
    body = float(bars.c[i] - bars.o[i])
    size = pips(abs(body), pip_size)
    if size + 1e-9 < min_body_pips or body == 0:
        return []
    return [Hit("long" if body > 0 else "short", detail={"body_pips": round(size, 1)})]


def hook_reversal_hits(
    bars: Bars, i: int, swings: list[Swing], min_leg_pips: float, pip_size: float
) -> list[Hit]:
    """After a move of at least min_leg_pips from the last swing, the signal bar opens beyond
    the previous bar's range and closes back inside it, against the move."""
    if i < 1 or not swings:
        return []
    anchor = swings[-1]
    start = anchor.index + 1
    if start >= i:
        return []
    o, c = float(bars.o[i]), float(bars.c[i])
    prev_h, prev_l = float(bars.h[i - 1]), float(bars.l[i - 1])
    if anchor.kind == "low":  # current move is up
        move = float(bars.h[start:i].max()) - anchor.price
        if pips(move, pip_size) + 1e-9 >= min_leg_pips and o > prev_h and prev_l <= c <= prev_h:
            return [Hit("short", detail={"move_pips": round(pips(move, pip_size), 1)})]
    else:  # current move is down
        move = anchor.price - float(bars.l[start:i].min())
        if pips(move, pip_size) + 1e-9 >= min_leg_pips and o < prev_l <= c <= prev_h:
            return [Hit("long", detail={"move_pips": round(pips(move, pip_size), 1)})]
    return []
