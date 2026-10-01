from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
import respx

from scanner.data.base import AuthCircuit, ProviderAuthError, ProviderBlockedError, completed
from scanner.data.oanda import MAX_CANDLES_PER_REQUEST, OandaClient, parse_time
from tests.conftest import load_fixture

HOST = "https://api-fxpractice.oanda.com"
URL = f"{HOST}/v3/instruments/EUR_USD/candles"
OANDA_TIME = "%Y-%m-%dT%H:%M:%S.000000000Z"


def client(circuit: AuthCircuit | None = None) -> OandaClient:
    return OandaClient("test-token", HOST, http=httpx.Client(), circuit=circuit)


@respx.mock
def test_candles_request_and_parsing() -> None:
    route = respx.get(URL).respond(json=load_fixture("http/oanda_candles_m15.json"))
    candles = client().candles("EUR_USD", "M15", count=3)

    req = route.calls.last.request
    assert req.headers["Authorization"] == "Bearer test-token"
    params = req.url.params
    assert params["price"] == "M"
    assert params["granularity"] == "M15"
    assert params["dailyAlignment"] == "17"
    assert params["alignmentTimezone"] == "America/New_York"
    assert params["weeklyAlignment"] == "Sunday"
    assert params["count"] == "3"

    assert len(candles) == 3
    first = candles[0]
    assert first.ts == datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
    assert first.o == Decimal("1.08390")
    assert first.c == Decimal("1.08401")
    assert first.volume == 412
    assert [c.complete for c in candles] == [True, True, False]


@respx.mock
def test_only_complete_candles_are_kept() -> None:
    respx.get(URL).respond(json=load_fixture("http/oanda_candles_m15.json"))
    kept = completed(client().candles("EUR_USD", "M15", count=3))
    assert [c.ts.minute for c in kept] == [0, 15]


def _page(start: datetime, n: int) -> dict[str, object]:
    return {
        "instrument": "EUR_USD",
        "granularity": "M15",
        "candles": [
            {
                "complete": True,
                "volume": 1,
                "time": (start + timedelta(minutes=15 * i)).strftime(
                    "%Y-%m-%dT%H:%M:%S.000000000Z"
                ),
                "mid": {"o": "1.1", "h": "1.1", "l": "1.1", "c": "1.1"},
            }
            for i in range(n)
        ],
    }


@respx.mock
def test_history_pages_by_5000_without_duplicates() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    second_start = start + timedelta(minutes=15 * MAX_CANDLES_PER_REQUEST)
    route = respx.get(URL).mock(
        side_effect=[
            httpx.Response(200, json=_page(start, MAX_CANDLES_PER_REQUEST)),
            httpx.Response(200, json=_page(second_start, 10)),
        ]
    )
    candles = client().history("EUR_USD", "M15", start)

    assert len(candles) == MAX_CANDLES_PER_REQUEST + 10
    assert len({c.ts for c in candles}) == len(candles)
    first_req, second_req = (call.request.url.params for call in route.calls)
    assert first_req["includeFirst"] == "true"
    assert first_req["count"] == "5000"
    assert second_req["includeFirst"] == "false"
    assert parse_time(second_req["from"]) == candles[MAX_CANDLES_PER_REQUEST - 1].ts


@respx.mock
def test_history_stops_at_end() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    respx.get(URL).respond(json=_page(start, 8))
    candles = client().history("EUR_USD", "M15", start, end=start + timedelta(hours=1))
    assert len(candles) == 4


@respx.mock
def test_unauthorized_pauses_calls_until_next_hour() -> None:
    now = [datetime(2026, 9, 30, 8, 20, tzinfo=UTC)]
    circuit = AuthCircuit("oanda", clock=lambda: now[0])
    route = respx.get(URL).respond(401, json=load_fixture("http/oanda_unauthorized.json"))
    c = client(circuit)

    with pytest.raises(ProviderAuthError):
        c.candles("EUR_USD", "M15", count=1)
    with pytest.raises(ProviderBlockedError):
        c.candles("EUR_USD", "M15", count=1)
    assert route.call_count == 1

    now[0] = datetime(2026, 9, 30, 9, 0, tzinfo=UTC)
    route.respond(json=load_fixture("http/oanda_candles_m15.json"))
    assert len(c.candles("EUR_USD", "M15", count=1)) == 3


def test_parse_time_handles_nanoseconds() -> None:
    ts = parse_time("2026-09-30T08:15:00.123456789Z")
    assert ts == datetime(2026, 9, 30, 8, 15, 0, 123456, tzinfo=UTC)
