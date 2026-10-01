from decimal import Decimal

import pytest

from scanner.instruments import default_pip_size, from_pips, provider_code, to_pips
from tests.conftest import load_fixture


def test_usdjpy_pips_fixture() -> None:
    fx = load_fixture("usdjpy_pips.json")
    pip = Decimal(fx["pip_size"])
    for case in fx["cases"]:
        assert from_pips(Decimal(case["pips"]), pip) == Decimal(case["price_distance"])
        assert to_pips(Decimal(case["price_distance"]), pip) == Decimal(case["pips"])


def test_eurusd_pips() -> None:
    assert to_pips(Decimal("0.00230"), Decimal("0.0001")) == Decimal("23")
    assert from_pips(Decimal("63"), Decimal("0.0001")) == Decimal("0.0063")


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("USD/JPY", "0.01"),
        ("EUR/JPY", "0.01"),
        ("GBP_JPY", "0.01"),
        ("EUR/USD", "0.0001"),
        ("USD/CHF", "0.0001"),
    ],
)
def test_default_pip_size(symbol: str, expected: str) -> None:
    assert default_pip_size(symbol) == Decimal(expected)


def test_provider_code() -> None:
    assert provider_code("eur/usd") == "EUR_USD"
