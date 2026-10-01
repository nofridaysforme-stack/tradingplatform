from datetime import date, datetime, timedelta
from typing import Any

import pytest

from scanner.signals.broker_adjust import adjust
from scanner.signals.lifecycle import BarView, TrackedSignal, expire_at_roll, result_pips, track
from tests.conftest import load_fixture, ruleset_from_snapshot

RS = ruleset_from_snapshot()
EXPIRY = RS.params("three_eight.expiry")
WINDOW = RS.params("three_eight.trading_window")
T0 = datetime.fromisoformat("2026-10-05T08:00:00+00:00")  # 04:00 New York


def sig(**kw: Any) -> TrackedSignal:
    base: dict[str, Any] = {
        "id": 1, "strategy": "three_eight", "direction": "long", "state": "open", "bar_ts": T0,
        "trading_day": date(2026, 10, 5), "entry": 1.0842, "stop": 1.0819, "target": 1.0905,
        "pip_size": 0.0001,
    }  # fmt: skip
    return TrackedSignal(**{**base, **kw})


def bar(k: int, o: float, h: float, low: float, c: float) -> BarView:
    return BarView(T0 + timedelta(minutes=15 * k), o, h, low, c)


def run(s: TrackedSignal, b: BarView, k: int = 1) -> Any:
    return track(s, b, bars_since=k, three_eight_expiry=EXPIRY, trading_window=WINDOW)


def test_same_bar_ambiguous_counts_as_a_loss() -> None:
    fx = load_fixture("same_bar_ambiguous.json")
    sd = fx["signal"]
    s = sig(**{**sd, "bar_ts": datetime.fromisoformat(sd["bar_ts"]),
               "trading_day": date.fromisoformat(sd["trading_day"])})  # fmt: skip
    ts, o, h, low, c = fx["bar"]
    out = run(s, BarView(datetime.fromisoformat(ts), o, h, low, c))
    exp = fx["expected"]
    assert (out.state, out.exit_price, out.result_pips) == (
        exp["state"], exp["exit_price"], exp["result_pips"],
    )  # fmt: skip


@pytest.mark.parametrize(
    ("direction", "h", "low", "state", "pips"),
    [
        ("long", 1.0906, 1.0830, "target_hit", 63.0),
        ("long", 1.0850, 1.0819, "stop_hit", -23.0),
        ("short", 1.0850, 1.0779, "target_hit", 63.0),
        ("short", 1.0865, 1.0830, "stop_hit", -23.0),
    ],
)
def test_target_and_stop(direction: str, h: float, low: float, state: str, pips: float) -> None:
    s = sig() if direction == "long" else sig(direction="short", stop=1.0865, target=1.0779)
    out = run(s, bar(1, 1.0842, h, low, 1.0840))
    assert out.state == state and out.result_pips == pips and out.closed


def test_signal_bar_itself_is_never_tracked() -> None:
    assert run(sig(), bar(0, 1.0842, 1.0950, 1.0800, 1.0840)).state is None


def test_expiry_after_max_bars_measured_at_close() -> None:
    out = run(sig(), bar(16, 1.0842, 1.0850, 1.0835, 1.0848), k=16)
    assert out.state == "expired" and out.exit_price == 1.0848 and out.result_pips == 6.0
    assert run(sig(), bar(15, 1.0842, 1.0850, 1.0835, 1.0848), k=15).state is None


def test_expiry_at_end_of_trading_window() -> None:
    # 10:30 close is still inside the primary window; the 10:45 close is after it.
    inside = bar(25, 1.0842, 1.0850, 1.0835, 1.0846)
    after = bar(26, 1.0842, 1.0850, 1.0835, 1.0846)
    big = {**EXPIRY, "max_bars": 100}
    assert (
        track(sig(), inside, bars_since=2, three_eight_expiry=big, trading_window=WINDOW).state
        is None
    )
    out = track(sig(), after, bars_since=3, three_eight_expiry=big, trading_window=WINDOW)
    assert out.state == "expired"


def test_fib_pivot_confirmation_and_reset() -> None:
    s = sig(strategy="fib_pivot", entry=1.0928, stop=1.0870, target=1.1103,
            confirmation=1.0959, reset=1.1103)  # fmt: skip
    out = track(s, bar(1, 1.0928, 1.0960, 1.0925, 1.0955), bars_since=1)
    assert out.state == "confirmed" and [e.kind for e in out.events] == ["confirmed"]
    s.state = "confirmed"
    s2 = TrackedSignal(**{**s.__dict__, "target": 1.1200})
    out = track(s2, bar(2, 1.0955, 1.1105, 1.0950, 1.1100), bars_since=2)
    assert [e.kind for e in out.events] == ["reset_reached"] and not out.closed


def test_fib_pivot_expires_at_the_day_roll() -> None:
    s = sig(strategy="fib_pivot", entry=1.0928, stop=1.0870, target=1.1014)
    roll = datetime.fromisoformat("2026-10-05T21:00:00+00:00")  # 17:00 New York
    out = track(s, BarView(roll, 1.0930, 1.0935, 1.0925, 1.0931), bars_since=52)
    assert out.state == "expired" and out.exit_price == 1.0930
    out = expire_at_roll(s, 1.0940, roll)
    assert out.state == "expired" and out.result_pips == 12.0


def test_closed_signals_are_left_alone() -> None:
    assert run(sig(state="target_hit"), bar(1, 1.0, 2.0, 0.5, 1.0)).events == []


def test_result_pips_uses_the_pip_size() -> None:
    assert result_pips("long", 150.10, 150.30, 0.01) == 20.0
    assert result_pips("short", 150.10, 150.30, 0.01) == -20.0


def test_broker_adjustment() -> None:
    a = adjust("long", 1.08420, 1.08190, 1.09050, 1.2, 0.0001)
    assert (a.entry, a.stop, a.target) == (1.08426, 1.08184, 1.09044)
    assert a.reward_risk == pytest.approx(61.8 / 24.2, abs=0.001)
    b = adjust("short", 1.08420, 1.08650, 1.07790, 1.0, 0.0001)
    assert (b.entry, b.stop, b.target) == (1.08415, 1.08655, 1.07795)
    jpy = adjust("long", 150.100, 149.900, 150.500, 2.0, 0.01, decimals=3)
    assert (jpy.entry, jpy.stop, jpy.target) == (150.11, 149.89, 150.49)
