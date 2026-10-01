"""DataProvider protocols, models, and errors (spec 04)."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel


class Candle(BaseModel):
    instrument: str  # provider code, "EUR_USD"
    granularity: str  # "M15", "D", "W", "M"
    ts: datetime  # bar open time, UTC
    o: Decimal
    h: Decimal
    l: Decimal  # noqa: E741 (spec field name)
    c: Decimal
    volume: int  # tick volume
    complete: bool


class DailyBar(BaseModel):
    ticker: str
    session_date: date
    o: Decimal
    h: Decimal
    l: Decimal  # noqa: E741 (spec field name)
    c: Decimal
    volume: int


class Split(BaseModel):
    ticker: str
    execution_date: date
    split_from: Decimal
    split_to: Decimal


class TickerRef(BaseModel):
    ticker: str
    name: str | None
    exchange: str | None


class ForexDataProvider(Protocol):
    def candles(
        self,
        instrument: str,
        granularity: str,
        start: datetime | None,
        end: datetime | None,
        count: int | None,
    ) -> list[Candle]: ...


class StockDataProvider(Protocol):
    def grouped_daily(self, session_date: date) -> list[DailyBar]: ...
    def ticker_history(self, ticker: str, start: date, end: date) -> list[DailyBar]: ...
    def splits_on(self, session_date: date) -> list[Split]: ...
    def active_common_stocks(self) -> list[TickerRef]: ...


class ProviderError(Exception):
    """A provider call failed."""


class ProviderAuthError(ProviderError):
    """The provider rejected the credentials (401 or 403)."""


class ProviderBlockedError(ProviderError):
    """Calls are paused after an auth failure until the next hour."""


def completed(candles: list[Candle]) -> list[Candle]:
    """Only completed bars are ever stored or evaluated."""
    return [c for c in candles if c.complete]


class AuthCircuit:
    """After a 401 or 403, stop calling the provider until the start of the next hour (spec 04)."""

    def __init__(self, provider: str, clock: Callable[[], datetime] | None = None) -> None:
        self.provider = provider
        self._clock = clock or (lambda: datetime.now(UTC))
        self.blocked_until: datetime | None = None

    def check(self) -> None:
        if self.blocked_until is not None:
            if self._clock() < self.blocked_until:
                raise ProviderBlockedError(
                    f"{self.provider} calls paused until {self.blocked_until.isoformat()}"
                )
            self.blocked_until = None

    def trip(self) -> None:
        now = self._clock()
        self.blocked_until = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
