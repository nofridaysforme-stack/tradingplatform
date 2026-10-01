"""Standard floor pivots (spec 06). H, L, C are the previous day's, week's, or month's values."""

from decimal import Decimal

THREE = Decimal(3)
TWO = Decimal(2)


def floor_pivots(h: Decimal, l: Decimal, c: Decimal) -> dict[str, Decimal]:  # noqa: E741
    p = (h + l + c) / THREE
    return {
        "P": p,
        "R1": TWO * p - l,
        "S1": TWO * p - h,
        "R2": p + (h - l),
        "S2": p - (h - l),
        "R3": h + TWO * (p - l),
        "S3": l - TWO * (h - p),
    }
