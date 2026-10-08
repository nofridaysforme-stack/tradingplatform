import json
from datetime import UTC, datetime, time
from pathlib import Path
from uuid import UUID, uuid4

from scanner.notify.health import HEARTBEAT_TEXT
from scanner.notify.messages import (
    SignalFacts,
    StockBuy,
    WatchRow,
    health_message,
    signal_message,
    stock_buy_message,
    stock_exit_message,
    stock_update_message,
    update_message,
    watch_message,
)
from scanner.notify.prefs import Channel, Kind, Prefs, in_quiet_hours, skip_reason

BASE = "https://desk.example.com"
NOON_NY = datetime(2026, 10, 7, 16, 0, tzinfo=UTC)  # 12:00 New York (EDT)
NIGHT_NY = datetime(2026, 10, 8, 3, 30, tzinfo=UTC)  # 23:30 New York


def test_signal_message_matches_spec_11() -> None:
    m = signal_message(
        SignalFacts(
            id="abc", strategy="three_eight", symbol="EUR/USD", direction="long", decimals=5,
            entry=1.0843, stop=1.0818, target=1.0904, reward_risk=2.44,
            indicators=["Pivots", "Candlestick formation", "Fibonacci"],
            has_provisional=True, broker="Broker A",
        ),
        BASE,
    )  # fmt: skip
    assert m.title == "Long EUR/USD (3/8 Formula)"
    assert m.body.split("\n") == [
        "Entry 1.08430  Stop 1.08180  Target 1.09040",
        "Reward to risk 2.4. Pivots, Candlestick formation, Fibonacci.",
        "Includes a provisional rule.",
        "Prices adjusted for Broker A.",
    ]
    assert m.url == f"{BASE}/signals/abc"
    assert "—" not in m.text() + m.html()


def test_fib_pivot_signal_uses_the_ladder() -> None:
    m = signal_message(
        SignalFacts(
            id="f", strategy="fib_pivot", symbol="EUR/USD", direction="long", decimals=5,
            entry=1.0925, stop=1.087, target=1.1014, reward_risk=1.62, indicators=[],
            has_provisional=False, broker=None, stop_at="pivot", target_at="take_profit",
        ),
        BASE,
    )  # fmt: skip
    assert m.body.split("\n")[0] == (
        "Break 1.09250 crossed. Stop 1.08700 (pivot). Target 1.10140 (take profit)."
    )
    assert m.body.endswith("Reference prices.")


def test_update_and_other_messages() -> None:
    hit = update_message(
        signal_id="s", symbol="EUR/USD", direction="long", kind="target_hit",
        at=datetime(2026, 10, 7, 14, 45, tzinfo=UTC), price=1.0904, decimals=5,
        result_pips=63, base_url=BASE,
    )  # fmt: skip
    assert (hit.title, hit.body) == ("EUR/USD long hit target", "+63 pips. Closed 10:45 New York.")
    confirmed = update_message(
        signal_id="s", symbol="EUR/USD", direction="short", kind="confirmed",
        at=datetime(2026, 10, 7, 14, 45, tzinfo=UTC), price=1.0781, decimals=5,
        result_pips=None, base_url=BASE,
    )  # fmt: skip
    assert confirmed.body == "At 1.07810, 10:45 New York."
    watch = watch_message([WatchRow("AAA", 12.5, 0.042, 4.9)], "2026-10-06", BASE)
    assert watch.title == "1 stock joined the watch list today"
    assert "AAA  close 12.50  4.2% below the 52-week high  APR 10-day 490%" in watch.body
    assert watch.url == f"{BASE}/stocks?session=2026-10-06&stage=watching"
    assert health_message("pair_stale:GBP/USD", "x", resolved=False, base_url=BASE).title == (
        "Health alert: no new bars for GBP/USD"
    )
    assert health_message("pair_stale:GBP/USD", "", resolved=True, base_url=BASE).title == (
        "Resolved: no new bars for GBP/USD"
    )


def test_stock_messages_match_spec_11() -> None:
    buy = stock_buy_message(
        StockBuy("s1", "ABCD", "Oct 8", 24.10, 22.895, 5, 32.535, 35, 20,
                 ["bullish candle (engulfing)", "MACD crossed up", "pivot hooked up",
                  "Stochastics crossed"], False),
        BASE,
    )  # fmt: skip
    assert buy.title == "Buy signal: ABCD at 24.10"
    assert buy.body == (
        "4 of 5 indicators: bullish candle (engulfing), MACD crossed up, pivot hooked up, "
        "Stochastics crossed.\nStop 22.90 (5%). Projection 32.54 (35% in 20 sessions). "
        "Close of Oct 8."
    )
    sell = stock_exit_message(
        ticker="ABCD", kind="trailing_stopped", price=29.83, entry=24.10, sessions=14,
        highest=31.40, voted=[], base_url=BASE,
    )  # fmt: skip
    assert (sell.title, sell.body) == (
        "Sell: ABCD trailing stop at 29.83",
        "+23.8% from 24.10 in 14 sessions. Highest close 31.40.",
    )
    stopped = stock_exit_message(
        ticker="ABCD", kind="stopped", price=22.80, entry=24.10, sessions=1, highest=24.10,
        voted=[], base_url=BASE, holding=True,
    )  # fmt: skip
    assert (stopped.title, stopped.body, stopped.url) == (
        "Sell: your holding ABCD stop at 22.80",
        "-5.4% from 24.10 in 1 session.",
        f"{BASE}/holdings",
    )
    trailing = stock_update_message(
        ticker="ABCD", kind="trailing_started", price=26.60, entry=24.10, stop=25.27,
        projection=32.54, horizon=20, base_url=BASE,
    )  # fmt: skip
    assert trailing.title == "ABCD: trailing stop started at 25.27"
    reached = stock_update_message(
        ticker="ABCD", kind="projection_reached", price=32.60, entry=24.10, stop=30.97,
        projection=32.54, horizon=20, base_url=BASE, holding=True,
    )  # fmt: skip
    assert reached.title == "Your holding ABCD reached its projection"


def test_quiet_hours_cross_midnight_in_the_owner_zone() -> None:
    p = Prefs(quiet_start=time(22, 0), quiet_end=time(7, 0))
    assert in_quiet_hours(p, NIGHT_NY, "America/New_York")
    assert not in_quiet_hours(p, NOON_NY, "America/New_York")
    # 03:30 UTC is 04:30 in London: still quiet there.
    assert in_quiet_hours(p, NIGHT_NY, "Europe/London")
    day = Prefs(quiet_start=time(9, 0), quiet_end=time(17, 0))
    assert in_quiet_hours(day, NOON_NY, "America/New_York")
    assert not in_quiet_hours(Prefs(), NIGHT_NY, "America/New_York")


def test_skip_reasons_follow_the_spec_order() -> None:
    pair = uuid4()
    p = Prefs(
        channels=["webpush", "telegram"], strategies=["three_eight"], instrument_ids=[pair],
        quiet_start=time(22, 0), quiet_end=time(7, 0), include_updates=False,
    )  # fmt: skip

    def skip(
        channel: Channel, kind: Kind, *, active: bool = True, at: datetime = NOON_NY,
        strategy: str | None = None, instrument_id: UUID | None = None,
    ) -> str | None:  # fmt: skip
        return skip_reason(
            p, active=active, channel=channel, kind=kind, at=at, timezone="America/New_York",
            strategy=strategy, instrument_id=instrument_id,
        )  # fmt: skip

    assert skip("webpush", "signal", strategy="three_eight", instrument_id=pair) is None
    assert skip("webpush", "signal", active=False) == "inactive"
    assert skip("email", "signal") == "channel_off"
    assert skip("webpush", "update") == "updates_off"
    assert skip("webpush", "signal", strategy="fib_pivot") == "strategy_off"
    assert skip("webpush", "signal", instrument_id=uuid4()) == "pair_off"
    assert skip("webpush", "signal", at=NIGHT_NY) == "quiet_hours"
    # Health ignores quiet hours and always reaches admins by email.
    assert skip("telegram", "health", at=NIGHT_NY) is None
    assert skip("email", "health", at=NIGHT_NY) is None
    # A test notification goes out whenever the owner presses the button.
    assert skip("webpush", "test", at=NIGHT_NY) is None


def test_heartbeat_alert_matches_the_shared_fixture() -> None:
    """The web service sends this one alert while the scanner is down (apps/web/lib/
    watchdog.ts); both sides read fixtures/heartbeat_alert.json so the wording stays the same."""
    fixture = json.loads((Path(__file__).parent / "fixtures" / "heartbeat_alert.json").read_text())
    assert fixture["body"] == HEARTBEAT_TEXT
    base = fixture["base_url"]
    m = health_message("heartbeat_stale", HEARTBEAT_TEXT, resolved=False, base_url=base)
    assert (m.title, m.body, m.url) == (fixture["title"], fixture["body"], fixture["url"])
    assert (m.text(), m.html()) == (fixture["text"], fixture["html"])
