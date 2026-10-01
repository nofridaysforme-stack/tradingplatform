"""Previous New York day high, low, and close (PDH, PDL)."""

from decimal import Decimal


def prev_day(h: Decimal, l: Decimal, c: Decimal) -> dict[str, Decimal]:  # noqa: E741
    return {"PDH": h, "PDL": l, "PDC": c}
