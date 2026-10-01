from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from scanner.data.base import Candle
from scanner.instruments import Instrument
from scanner.levels.compute import build_levels
from scanner.levels.fib_pivot import closest_fibonacci, fib_pivot_ladder, offsets_from
from scanner.levels.floor_pivots import floor_pivots
from scanner.levels.prev_day import prev_day
from tests.conftest import load_fixture

FIVE = Decimal("0.00001")
FIB_PARAMS = {"min_fib": 13, "max_fib": 987, "forex_unit": "pip"}


@pytest.mark.parametrize("case", load_fixture("floor_pivots_basic.json")["cases"])
def test_floor_pivots_match_hand_calculation(case: dict[str, object]) -> None:
    got = floor_pivots(Decimal(case["h"]), Decimal(case["l"]), Decimal(case["c"]))  # type: ignore[arg-type]
    expected = case["expected"]
    assert isinstance(expected, dict)
    for name, value in expected.items():
        assert got[name].quantize(FIVE) == Decimal(value), name


def test_fib_pivot_notes_example() -> None:
    fx = load_fixture("fib_pivot_notes_example.json")
    ladder = fib_pivot_ladder(
        Decimal(fx["h"]), Decimal(fx["l"]), Decimal(fx["c"]), Decimal(fx["unit"]),
        min_fib=13, max_fib=987,
    )  # fmt: skip
    exp = fx["expected"]
    assert ladder.range_units == Decimal(exp["range_units"])
    assert ladder.fib == exp["fib"]
    assert ladder.offsets == exp["offsets"]
    for side in ("up", "down"):
        for name, value in exp[side].items():
            assert getattr(ladder, side)[name] == Decimal(value), (side, name)


def test_fib_pivot_eurusd_ladder() -> None:
    fx = load_fixture("fib_pivot_eurusd.json")
    ladder = fib_pivot_ladder(
        Decimal(fx["h"]), Decimal(fx["l"]), Decimal(fx["c"]), Decimal(fx["unit"]),
        min_fib=13, max_fib=987,
    )  # fmt: skip
    exp = fx["expected"]
    assert ladder.range_units == Decimal(exp["range_units"])
    assert ladder.fib == exp["fib"]
    assert ladder.offsets == exp["offsets"]
    assert ladder.pivot == Decimal(exp["pivot"])
    for side in ("up", "down"):
        for name, value in exp[side].items():
            assert getattr(ladder, side)[name] == Decimal(value), (side, name)


@pytest.mark.parametrize(
    ("range_units", "expected"),
    [
        ("66", 55),
        ("72", 89),  # 72 is 17 from 55 and 17 from 89: ties go to the larger number
        ("71.9", 55),
        ("3", 13),  # clamped to min_fib
        ("5000", 987),  # clamped to max_fib
        ("144", 144),
    ],
)
def test_closest_fibonacci(range_units: str, expected: int) -> None:
    assert closest_fibonacci(Decimal(range_units), 13, 987) == expected


def test_offsets_extend_past_max_fib() -> None:
    assert offsets_from(987) == [987, 1597, 2584, 4181]
    assert offsets_from(13) == [13, 21, 34, 55]


def test_closest_fibonacci_rejects_empty_range() -> None:
    with pytest.raises(ValueError, match="no Fibonacci number"):
        closest_fibonacci(Decimal(50), 40, 50)


def test_prev_day() -> None:
    assert prev_day(Decimal("1.1"), Decimal("1.0"), Decimal("1.05")) == {
        "PDH": Decimal("1.1"),
        "PDL": Decimal("1.0"),
        "PDC": Decimal("1.05"),
    }


def _candle(gran: str, h: str, l: str, c: str) -> Candle:  # noqa: E741
    return Candle(
        instrument="EUR_USD", granularity=gran, ts=datetime(2026, 9, 28, 21, tzinfo=UTC),
        o=Decimal(c), h=Decimal(h), l=Decimal(l), c=Decimal(c), volume=1, complete=True,
    )  # fmt: skip


def test_build_levels_produces_every_set() -> None:
    inst = Instrument(
        id=uuid4(), symbol="EUR/USD", provider_code="EUR_USD",
        pip_size=Decimal("0.0001"), display_decimals=5,
    )  # fmt: skip
    sets = build_levels(
        inst,
        daily=_candle("D", "1.08950", "1.08290", "1.08700"),
        weekly=_candle("W", "1.09500", "1.07500", "1.08800"),
        monthly=None,
        fib_params=FIB_PARAMS,
    )
    assert set(sets) == {"daily", "prev_day", "fib_pivot", "weekly"}
    assert sets["daily"]["P"] == 1.08646667
    assert sets["prev_day"]["PDH"] == 1.0895
    assert sets["fib_pivot"]["up"]["break"] == 1.0925
    assert sets["fib_pivot"]["fib"] == 55
    assert sets["daily"]["source"]["granularity"] == "D"


def test_build_levels_rejects_unknown_unit() -> None:
    inst = Instrument(
        id=uuid4(), symbol="EUR/USD", provider_code="EUR_USD",
        pip_size=Decimal("0.0001"), display_decimals=5,
    )  # fmt: skip
    with pytest.raises(ValueError, match="unsupported"):
        build_levels(
            inst,
            daily=_candle("D", "1.1", "1.0", "1.05"),
            weekly=None,
            monthly=None,
            fib_params={**FIB_PARAMS, "forex_unit": "cent"},
        )
