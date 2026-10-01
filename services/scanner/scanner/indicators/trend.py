"""Trend state: up when the last two swing highs and last two swing lows are both higher,
down when both lower, otherwise none (spec 06)."""

from typing import Literal

from scanner.indicators.swings import Swing

Trend = Literal["up", "down", "none"]


def trend_state(swings: list[Swing]) -> Trend:
    highs = [s.price for s in swings if s.kind == "high"][-2:]
    lows = [s.price for s in swings if s.kind == "low"][-2:]
    if len(highs) < 2 or len(lows) < 2:
        return "none"
    if highs[1] > highs[0] and lows[1] > lows[0]:
        return "up"
    if highs[1] < highs[0] and lows[1] < lows[0]:
        return "down"
    return "none"
