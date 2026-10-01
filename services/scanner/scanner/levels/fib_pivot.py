"""Fibonacci Pivot Point ladder (spec 07, rule fib_pivot.levels).

1. Range in units = (prior day high - prior day low) / unit. Forex unit is the pip.
2. Closest Fibonacci number (ties go to the larger), clamped to [min_fib, max_fib].
3. Offsets F0..F3 are that number and the next three.
4. Pivot = prior day close. Break, Confirmation, Take Profit, Reset at Pivot +/- F0..F3.
"""

from decimal import Decimal

from pydantic import BaseModel

LEVEL_NAMES = ("break", "confirmation", "take_profit", "reset")


def fibonacci_numbers(limit: int) -> list[int]:
    """Distinct Fibonacci numbers 1, 2, 3, 5, 8, ... up to and including the first >= limit."""
    seq = [1, 2]
    while seq[-1] < limit:
        seq.append(seq[-1] + seq[-2])
    return seq


def closest_fibonacci(range_units: Decimal, min_fib: int, max_fib: int) -> int:
    allowed = [f for f in fibonacci_numbers(max_fib) if min_fib <= f <= max_fib]
    if not allowed:
        raise ValueError(f"no Fibonacci number between {min_fib} and {max_fib}")
    # Ties go to the larger number: sort key prefers smaller distance, then larger value.
    return min(allowed, key=lambda f: (abs(Decimal(f) - range_units), -f))


def offsets_from(fib: int) -> list[int]:
    seq = fibonacci_numbers(fib)
    i = seq.index(fib)
    while len(seq) < i + 4:
        seq.append(seq[-1] + seq[-2])
    return seq[i : i + 4]


class FibPivotLadder(BaseModel):
    range_units: Decimal
    fib: int
    offsets: list[int]
    unit: Decimal
    pivot: Decimal
    up: dict[str, Decimal]  # break, confirmation, take_profit, reset above the pivot
    down: dict[str, Decimal]  # the same levels below the pivot


def fib_pivot_ladder(
    h: Decimal,
    l: Decimal,  # noqa: E741
    c: Decimal,
    unit: Decimal,
    *,
    min_fib: int,
    max_fib: int,
) -> FibPivotLadder:
    range_units = (h - l) / unit
    fib = closest_fibonacci(range_units, min_fib, max_fib)
    offsets = offsets_from(fib)
    up = {name: c + off * unit for name, off in zip(LEVEL_NAMES, offsets, strict=True)}
    down = {name: c - off * unit for name, off in zip(LEVEL_NAMES, offsets, strict=True)}
    return FibPivotLadder(
        range_units=range_units,
        fib=fib,
        offsets=offsets,
        unit=unit,
        pivot=c,
        up=up,
        down=down,
    )
