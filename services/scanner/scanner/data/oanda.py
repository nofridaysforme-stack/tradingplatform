"""OANDA v20 REST adapter for forex candles (spec 04)."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from scanner.data.base import (
    AuthCircuit,
    Candle,
    ProviderAuthError,
    ProviderError,
)

log = logging.getLogger(__name__)

MAX_CANDLES_PER_REQUEST = 5000
ALIGNMENT_PARAMS = {
    "price": "M",
    "dailyAlignment": "17",
    "alignmentTimezone": "America/New_York",
    "weeklyAlignment": "Sunday",
}


def _rfc3339(ts: datetime) -> str:
    if ts.tzinfo is None:
        raise ValueError("naive datetime")
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_time(value: str) -> datetime:
    """OANDA returns RFC 3339 with nanoseconds, e.g. 2026-09-30T04:00:00.000000000Z."""
    head, _, frac = value.rstrip("Z").partition(".")
    micros = (frac + "000000")[:6]
    return datetime.fromisoformat(f"{head}.{micros}").replace(tzinfo=UTC)


def parse_candle(instrument: str, granularity: str, raw: dict[str, Any]) -> Candle:
    mid = raw["mid"]
    return Candle(
        instrument=instrument,
        granularity=granularity,
        ts=parse_time(raw["time"]),
        o=Decimal(mid["o"]),
        h=Decimal(mid["h"]),
        l=Decimal(mid["l"]),
        c=Decimal(mid["c"]),
        volume=int(raw.get("volume", 0)),
        complete=bool(raw["complete"]),
    )


class OandaClient:
    """Implements ForexDataProvider."""

    def __init__(
        self,
        token: str,
        host: str,
        *,
        http: httpx.Client | None = None,
        circuit: AuthCircuit | None = None,
    ) -> None:
        self._http = http or httpx.Client(timeout=httpx.Timeout(20.0))
        self._host = host.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept-Datetime-Format": "RFC3339",
        }
        self.circuit = circuit or AuthCircuit("oanda")

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        self.circuit.check()
        resp = self._http.get(f"{self._host}{path}", params=params, headers=self._headers)
        if resp.status_code in (401, 403):
            self.circuit.trip()
            raise ProviderAuthError(f"oanda returned {resp.status_code}")
        if resp.status_code != 200:
            raise ProviderError(f"oanda returned {resp.status_code}: {resp.text[:200]}")
        data: dict[str, Any] = resp.json()
        return data

    def candles(
        self,
        instrument: str,
        granularity: str,
        start: datetime | None = None,
        end: datetime | None = None,
        count: int | None = None,
    ) -> list[Candle]:
        """One request. Returns complete and incomplete candles; callers keep complete ones."""
        params = {**ALIGNMENT_PARAMS, "granularity": granularity}
        if start is not None:
            params["from"] = _rfc3339(start)
        if end is not None:
            params["to"] = _rfc3339(end)
        if count is not None:
            params["count"] = str(min(count, MAX_CANDLES_PER_REQUEST))
        data = self._get(f"/v3/instruments/{instrument}/candles", params)
        return [parse_candle(instrument, granularity, c) for c in data.get("candles", [])]

    def history(
        self, instrument: str, granularity: str, start: datetime, end: datetime | None = None
    ) -> list[Candle]:
        """Pages forward from start in requests of up to 5000 candles, stopping at end."""
        out: list[Candle] = []
        params = {**ALIGNMENT_PARAMS, "granularity": granularity}
        params["count"] = str(MAX_CANDLES_PER_REQUEST)
        cursor = start
        include_first = True
        while True:
            params["from"] = _rfc3339(cursor)
            params["includeFirst"] = "true" if include_first else "false"
            data = self._get(f"/v3/instruments/{instrument}/candles", params)
            page = [parse_candle(instrument, granularity, c) for c in data.get("candles", [])]
            for candle in page:
                if end is not None and candle.ts >= end:
                    return out
                out.append(candle)
            if len(page) < MAX_CANDLES_PER_REQUEST:
                return out
            cursor = page[-1].ts
            include_first = False
            log.debug("oanda paging %s %s from %s", instrument, granularity, cursor.isoformat())
