"""Instruments and pip math (spec 04). Pips always come from the instrument's pip_size."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

JPY_PIP_SIZE = Decimal("0.01")
DEFAULT_PIP_SIZE = Decimal("0.0001")


class Instrument(BaseModel):
    id: UUID
    symbol: str  # 'EUR/USD'
    provider_code: str  # 'EUR_USD'
    pip_size: Decimal
    display_decimals: int
    enabled: bool = True


def to_pips(price_distance: Decimal, pip_size: Decimal) -> Decimal:
    return price_distance / pip_size


def from_pips(pips: Decimal, pip_size: Decimal) -> Decimal:
    return pips * pip_size


def default_pip_size(symbol: str) -> Decimal:
    """Pre-fill for the add-instrument form: any pair quoted in JPY uses 0.01."""
    quote = symbol.replace("_", "/").split("/")[-1].upper()
    return JPY_PIP_SIZE if quote == "JPY" else DEFAULT_PIP_SIZE


def provider_code(symbol: str) -> str:
    return symbol.replace("/", "_").upper()
