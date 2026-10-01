"""Massive (formerly Polygon.io) adapter for US stock bars, tickers, and splits (spec 04)."""

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx

from scanner.data.base import (
    AuthCircuit,
    DailyBar,
    ProviderAuthError,
    ProviderError,
    Split,
    TickerRef,
)
from scanner.time import NEW_YORK

log = logging.getLogger(__name__)

CALLS_PER_WINDOW = 5
WINDOW_SECONDS = 60.0


class RateLimiter:
    """At most `calls` calls in any rolling `window` seconds. Thread safe."""

    def __init__(
        self,
        calls: int = CALLS_PER_WINDOW,
        window: float = WINDOW_SECONDS,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.calls = calls
        self.window = window
        self._clock = clock
        self._sleep = sleep
        self._stamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            while True:
                now = self._clock()
                while self._stamps and now - self._stamps[0] >= self.window:
                    self._stamps.popleft()
                if len(self._stamps) < self.calls:
                    self._stamps.append(now)
                    return
                self._sleep(self.window - (now - self._stamps[0]))


# Every Massive call in the process goes through this one limiter.
SHARED_LIMITER = RateLimiter()


def _session_date(ms: int) -> date:
    """Daily aggregate timestamps are the start of the session day; read them in New York."""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).astimezone(NEW_YORK).date()


def _bar(ticker: str, session: date, raw: dict[str, Any]) -> DailyBar:
    return DailyBar(
        ticker=ticker,
        session_date=session,
        o=Decimal(str(raw["o"])),
        h=Decimal(str(raw["h"])),
        l=Decimal(str(raw["l"])),
        c=Decimal(str(raw["c"])),
        volume=int(raw.get("v", 0)),
    )


class MassiveClient:
    """Implements StockDataProvider."""

    def __init__(
        self,
        api_key: str,
        host: str,
        *,
        http: httpx.Client | None = None,
        limiter: RateLimiter | None = None,
        circuit: AuthCircuit | None = None,
    ) -> None:
        self._http = http or httpx.Client(timeout=httpx.Timeout(60.0))
        self._host = host.rstrip("/")
        # Header auth keeps the key out of URLs and logs.
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._limiter = limiter or SHARED_LIMITER
        self.circuit = circuit or AuthCircuit("massive")

    def _get_url(self, url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        self.circuit.check()
        self._limiter.acquire()
        resp = self._http.get(url, params=params, headers=self._headers)
        if resp.status_code in (401, 403):
            self.circuit.trip()
            raise ProviderAuthError(f"massive returned {resp.status_code}")
        if resp.status_code != 200:
            raise ProviderError(f"massive returned {resp.status_code}: {resp.text[:200]}")
        data: dict[str, Any] = resp.json()
        return data

    def _get_all(self, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        """Follows next_url; each page counts against the rate limit."""
        results: list[dict[str, Any]] = []
        data = self._get_url(f"{self._host}{path}", params)
        results.extend(data.get("results") or [])
        while next_url := data.get("next_url"):
            data = self._get_url(next_url)
            results.extend(data.get("results") or [])
        return results

    def grouped_daily(self, session_date: date) -> list[DailyBar]:
        """Every US stock's bar for one session. Empty if the session is not published yet."""
        path = f"/v2/aggs/grouped/locale/us/market/stocks/{session_date.isoformat()}"
        data = self._get_url(f"{self._host}{path}", {"adjusted": "true"})
        return [_bar(r["T"], session_date, r) for r in data.get("results") or []]

    def ticker_history(self, ticker: str, start: date, end: date) -> list[DailyBar]:
        path = f"/v2/aggs/ticker/{ticker}/range/1/day/{start.isoformat()}/{end.isoformat()}"
        rows = self._get_all(path, {"adjusted": "true", "sort": "asc", "limit": "50000"})
        return [_bar(ticker, _session_date(int(r["t"])), r) for r in rows]

    def splits_on(self, session_date: date) -> list[Split]:
        rows = self._get_all(
            "/v3/reference/splits", {"execution_date": session_date.isoformat(), "limit": "1000"}
        )
        return [
            Split(
                ticker=r["ticker"],
                execution_date=date.fromisoformat(r["execution_date"]),
                split_from=Decimal(str(r["split_from"])),
                split_to=Decimal(str(r["split_to"])),
            )
            for r in rows
        ]

    def active_common_stocks(self) -> list[TickerRef]:
        rows = self._get_all(
            "/v3/reference/tickers",
            {"market": "stocks", "type": "CS", "active": "true", "limit": "1000"},
        )
        return [
            TickerRef(ticker=r["ticker"], name=r.get("name"), exchange=r.get("primary_exchange"))
            for r in rows
        ]
