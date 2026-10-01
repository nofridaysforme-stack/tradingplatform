from datetime import date
from decimal import Decimal

import httpx
import pytest
import respx

from scanner.data.base import AuthCircuit, ProviderAuthError, ProviderBlockedError
from scanner.data.massive import MassiveClient, RateLimiter
from tests.conftest import load_fixture

HOST = "https://api.massive.com"


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def client(limiter: RateLimiter | None = None, circuit: AuthCircuit | None = None) -> MassiveClient:
    return MassiveClient(
        "test-key",
        HOST,
        http=httpx.Client(),
        limiter=limiter or RateLimiter(calls=1000, window=60),
        circuit=circuit,
    )


@respx.mock
def test_grouped_daily() -> None:
    route = respx.get(f"{HOST}/v2/aggs/grouped/locale/us/market/stocks/2026-09-29").respond(
        json=load_fixture("http/massive_grouped_2026-09-29.json")
    )
    bars = client().grouped_daily(date(2026, 9, 29))

    req = route.calls.last.request
    assert req.url.params["adjusted"] == "true"
    assert req.headers["Authorization"] == "Bearer test-key"
    assert "test-key" not in str(req.url)
    assert [b.ticker for b in bars] == ["AAPL", "CAMP", "ZZZ"]
    camp = bars[1]
    assert camp.session_date == date(2026, 9, 29)
    assert camp.c == Decimal("9.10")
    assert camp.h == Decimal("9.21")
    assert camp.volume == 812345


@respx.mock
def test_grouped_daily_not_published_yet() -> None:
    respx.get(f"{HOST}/v2/aggs/grouped/locale/us/market/stocks/2026-09-30").respond(
        json=load_fixture("http/massive_grouped_empty.json")
    )
    assert client().grouped_daily(date(2026, 9, 30)) == []


@respx.mock
def test_ticker_history_reads_session_dates_in_new_york() -> None:
    respx.get(f"{HOST}/v2/aggs/ticker/CAMP/range/1/day/2026-09-01/2026-09-29").respond(
        json=load_fixture("http/massive_ticker_history_camp.json")
    )
    bars = client().ticker_history("CAMP", date(2026, 9, 1), date(2026, 9, 29))
    assert [b.session_date for b in bars] == [date(2026, 9, 25), date(2026, 9, 29)]


@respx.mock
def test_splits_on() -> None:
    route = respx.get(f"{HOST}/v3/reference/splits").respond(
        json=load_fixture("http/massive_splits_2026-09-29.json")
    )
    splits = client().splits_on(date(2026, 9, 29))
    assert route.calls.last.request.url.params["execution_date"] == "2026-09-29"
    assert len(splits) == 1
    assert splits[0].ticker == "CAMP"
    assert splits[0].split_to == Decimal(2)


@respx.mock
def test_active_common_stocks_follows_next_url() -> None:
    page1 = respx.get(f"{HOST}/v3/reference/tickers", params={"type": "CS"}).respond(
        json=load_fixture("http/massive_tickers_page1.json")
    )
    page2 = respx.get(f"{HOST}/v3/reference/tickers", params={"cursor": "YWN0aXZlPXRydWU"}).respond(
        json=load_fixture("http/massive_tickers_page2.json")
    )
    refs = client().active_common_stocks()

    params = page1.calls.last.request.url.params
    assert (params["market"], params["active"], params["limit"]) == ("stocks", "true", "1000")
    assert page2.call_count == 1
    assert page2.calls.last.request.headers["Authorization"] == "Bearer test-key"
    assert [(r.ticker, r.exchange) for r in refs] == [
        ("AAPL", "XNAS"),
        ("CAMP", "XNAS"),
        ("IBM", "XNYS"),
    ]


def test_rate_limiter_allows_five_calls_per_rolling_minute() -> None:
    clock = FakeClock()
    limiter = RateLimiter(calls=5, window=60, clock=clock, sleep=clock.sleep)
    for _ in range(5):
        limiter.acquire()
    assert clock.slept == []

    clock.now = 10
    limiter.acquire()  # sixth call waits until the first leaves the window
    assert clock.slept == [50]
    assert clock.now == 60

    for _ in range(4):
        limiter.acquire()
    assert clock.now == 60  # calls 2 to 5 were at t=0, so they all expired at t=60


@respx.mock
def test_every_page_goes_through_the_shared_limiter() -> None:
    clock = FakeClock()
    limiter = RateLimiter(calls=1, window=60, clock=clock, sleep=clock.sleep)
    respx.get(f"{HOST}/v3/reference/tickers", params={"type": "CS"}).respond(
        json=load_fixture("http/massive_tickers_page1.json")
    )
    respx.get(f"{HOST}/v3/reference/tickers", params={"cursor": "YWN0aXZlPXRydWU"}).respond(
        json=load_fixture("http/massive_tickers_page2.json")
    )
    client(limiter).active_common_stocks()
    assert clock.slept == [60]


@respx.mock
def test_forbidden_pauses_calls() -> None:
    route = respx.get(f"{HOST}/v3/reference/splits").respond(403, json={"status": "NOT_AUTHORIZED"})
    c = client()
    with pytest.raises(ProviderAuthError):
        c.splits_on(date(2026, 9, 29))
    with pytest.raises(ProviderBlockedError):
        c.splits_on(date(2026, 9, 29))
    assert route.call_count == 1
