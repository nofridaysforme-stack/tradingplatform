"""The stock momentum system (spec 08, revised 2026-10-08)."""

from datetime import date, timedelta
from decimal import Decimal

import numpy as np

from scanner.backtest.stocks import replay
from scanner.rules.registry import RuleSet, derive
from scanner.strategies import stock_momentum as sm
from scanner.strategies.stock_screener import DayBar
from tests.conftest import ruleset_from_snapshot

D = Decimal
RULES = ruleset_from_snapshot()
# Oscillators over 5 sessions, so a short synthetic pullback can move them; the defaults are
# 14 sessions (spec 08), which a pullback of under 10 percent rarely moves this far.
FAST = derive(
    RULES, {"stocks.ind_stoch": {"k_period": 5, "k_slowing": 1}, "stocks.ind_rsi": {"period": 5}}
)


def _q(x: float) -> Decimal:
    return D(str(round(x, 4)))


def bars_of(rows: list[tuple[float, float]], start: date = date(2024, 1, 1)) -> list[DayBar]:
    """(open, close) per weekday session; highs and lows just outside the body."""
    out, d = [], start
    for o, c in rows:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        hi, lo = max(o, c) * 1.004, min(o, c) * 0.996
        out.append(DayBar(d, _q(hi), _q(lo), _q(c), 500_000, _q(o)))
        d += timedelta(days=1)
    return out


def closes(values: list[float]) -> list[DayBar]:
    return bars_of([(v, v) for v in values])


def momentum_stock() -> list[DayBar]:
    """A year rising from 3 to 6, a 22 percent run in 10 sessions, a 7-session pullback inside
    the zone, an engulfing bounce, a climb, then a fall."""
    rows, p = [], 3.0
    for k in range(250):
        n = 3 + 3 * (k + 1) / 250
        rows.append((p, n))
        p = n
    for step, count in [(1.02, 10), (0.988, 7)]:
        for _ in range(count):
            rows.append((p, p * step))
            p *= step
    rows.append((p * 0.995, p * 1.025))  # bullish engulfing
    p *= 1.025
    for step, count in [(1.015, 12), (0.975, 8)]:
        for _ in range(count):
            rows.append((p, p * step))
            p *= step
    return bars_of(rows)


def no_fire(n: int) -> sm.Fired:
    return sm.Fired(np.zeros(n, dtype=np.bool_), np.zeros(n, dtype=np.bool_), {})


def fires(n: int, buy: list[int] = [], sell: list[int] = []) -> sm.Fired:  # noqa: B006
    f = no_fire(n)
    f.buy[buy] = True
    f.sell[sell] = True
    return f


def test_crosses_need_the_previous_session_on_the_other_side() -> None:
    a = np.array([1.0, 2.0, 3.0, 1.0, np.nan, 3.0])
    b = np.array([2.0, 2.0, 2.0, 2.0, 2.0, 2.0])
    assert sm.cross_above(a, b).tolist() == [False, False, True, False, False, False]
    assert sm.cross_below(a, b).tolist() == [False, False, False, True, False, False]


def test_momentum_threshold_is_35_percent_in_20_sessions() -> None:
    assert sm.momentum_threshold(RULES) == D("4.55")
    assert sm.momentum_threshold(derive(RULES, {"stocks.momentum": {"projection_pct": 30}})) == (
        D("3.9")
    )


def test_the_funnel_buys_after_the_pullback_and_sells_on_the_vote() -> None:
    bars = momentum_stock()
    fired = sm.indicators(bars, FAST)
    state = sm.WatchState()
    days = {i: sm.step("SYN", bars, i, FAST, state) for i in range(249, 271)}
    assert [i for i, d in days.items() if d.joined] == [257]  # 10-day APR passes 455%
    assert days[262].watching and not days[262].momentum  # still waiting for the pullback
    assert not days[270].watching  # 10 sessions after its last momentum pass
    # The first buy is 267; the votes stay in the window for two more sessions, but by then
    # the stock is held (the replay below opens one position).
    assert next(i for i in range(258, 270) if sm.is_buy(bars, fired, days[i], FAST)) == 267
    votes = {v.key for v in sm.buy_votes(bars, fired, 267, FAST)}
    assert votes == {"stocks.ind_candle", "stocks.ind_pivot", "stocks.ind_rsi", "stocks.ind_stoch"}
    candle = next(v for v in sm.buy_votes(bars, fired, 267, FAST) if v.key == "stocks.ind_candle")
    assert "engulfing" in candle.names

    trades, joins = replay("SYN", bars, FAST)
    assert joins == 1
    (t,) = trades
    assert (t.buy_session, t.entry, t.reason, t.sessions) == (
        bars[267].session_date, D("6.8893"), "sold", 13,
    )  # fmt: skip
    assert t.exit_price == D("8.0311")
    assert round(float(t.result_pct or 0), 4) == 0.1657
    assert t.has_provisional  # RSI and the candle list are provisional


def test_default_oscillators_rarely_vote_in_a_shallow_pullback() -> None:
    """Spec 08 note: in a pullback of under 10 percent, RSI(14) stays far above 30 and
    Stochastics(14) far above 20, so a buy usually comes from the other three indicators."""
    bars = momentum_stock()
    fired = sm.indicators(bars, RULES)
    assert not fired["stocks.ind_rsi"].buy[255:275].any()
    assert not fired["stocks.ind_stoch"].buy[255:275].any()
    assert replay("SYN", bars, RULES)[0] == []


def test_votes_count_distinct_indicators_in_the_window_after_entry() -> None:
    bars = closes([10.0] * 10)
    fired = {
        "stocks.ind_macd": fires(10, buy=[3, 5], sell=[8]),
        "stocks.ind_pivot": fires(10, buy=[6], sell=[9]),
        "stocks.ind_rsi": fires(10, buy=[2], sell=[6]),
    }
    found = sm.votes(bars, fired, 6, "buy", 3, RULES)
    assert {(v.key, v.index) for v in found} == {("stocks.ind_macd", 5), ("stocks.ind_pivot", 6)}
    assert not sm.vote_passes(found, "stocks.buy_vote", RULES)
    assert sm.vote_passes(
        found, "stocks.buy_vote", derive(RULES, {"stocks.buy_vote": {"min_votes": 2}})
    )
    sells = sm.votes(bars, fired, 9, "sell", 3, RULES, after=6)
    assert {v.key for v in sells} == {"stocks.ind_macd", "stocks.ind_pivot"}  # RSI is at entry


def test_a_bullish_candle_counts_only_inside_the_pullback_zone() -> None:
    bars = momentum_stock()
    fired = {"stocks.ind_candle": fires(len(bars), buy=[267, 287])}
    assert [v.index for v in sm.votes(bars, fired, 267, "buy", 3, RULES)] == [267]
    assert sm.votes(bars, fired, 287, "buy", 3, RULES) == []  # over 10 percent below the high


def test_trailing_stop_worked_example() -> None:
    """Spec 08: buy at 20.00, fixed stop 19.00; at 22.00 the trailing stop starts at 20.90;
    at 26.00 it is 24.70; a close of 24.70 exits there, +23.5 percent."""
    bars = closes([20.0, 21.0, 22.0, 26.0, 25.0, 24.70, 30.0])
    p = sm.plan(D("20.0"), RULES)
    assert (p.stop_initial, p.projection) == (D("19.000"), D("27.00"))
    t = sm.track(bars, {}, 0, p, RULES)
    assert t.exit is not None and (t.exit.kind, t.exit.index, t.exit.price) == (
        "trailing_stopped", 5, D("24.7"),
    )  # fmt: skip
    assert sm.result_pct(p.entry, t.exit.price) == D("0.235")
    assert [(e.kind, e.index) for e in t.events] == [
        ("trailing_started", 2), ("trailing_stopped", 5),
    ]  # fmt: skip
    assert t.events[0].detail == {"highest_close": "22.0"}
    after_22 = sm.track(bars, {}, 0, p, RULES, end=2)
    assert after_22.stop_now == D("20.900") and after_22.trailing_active


def test_fixed_stop_beats_a_sell_vote_on_the_same_session() -> None:
    bars = closes([20.0, 19.5, 19.0, 18.0])
    fired = {k: fires(4, sell=[2]) for k in sm.INDICATORS}
    t = sm.track(bars, fired, 0, sm.plan(D("20"), RULES), RULES)
    assert t.exit is not None and (t.exit.kind, t.exit.index) == ("stopped", 2)


def test_sell_vote_and_projection_and_horizon() -> None:
    bars = closes([20.0, 21.0, 27.5, 27.0, 26.8])
    sold = {
        k: fires(5, sell=[4]) for k in ("stocks.ind_macd", "stocks.ind_pivot", "stocks.ind_rsi")
    }
    t = sm.track(bars, sold, 0, sm.plan(D("20"), RULES), RULES)
    assert [e.kind for e in t.events] == ["trailing_started", "projection_reached", "sold"]
    assert t.exit is not None and t.exit.detail["votes"] == [
        "stocks.ind_macd", "stocks.ind_pivot", "stocks.ind_rsi",
    ]  # fmt: skip
    slow = closes([20.0, 20.5, 20.6, 20.4])
    late = sm.track(slow, {}, 0, sm.plan(D("20"), RULES, D(35), 2), RULES)
    assert [(e.kind, e.index) for e in late.events] == [("horizon_passed", 2)]
    assert late.exit is None and late.stop_now == D("19.000")


def test_switched_off_stops_never_exit() -> None:
    off: RuleSet = derive(RULES, disabled={"stocks.stop_loss", "stocks.trailing_stop"})
    t = sm.track(closes([20.0, 25.0, 10.0]), {}, 0, sm.plan(D("20"), off), off)
    assert t.exit is None and t.stop_now is None and not t.trailing_active


def test_holding_projection_matches_entry_points_and_sales_targets() -> None:
    p = sm.plan(D("23.13"), RULES)
    assert (p.projection, p.daily_target, p.weekly_target) == (
        D("31.2255"), D("0.404775"), D("2.023875"),
    )  # fmt: skip
    assert p.stop_initial == D("21.97350")


def test_a_stock_can_rejoin_the_watch_list_only_after_its_exit() -> None:
    bars = momentum_stock()
    blocked = sm.WatchState(blocked_through=262)
    days = [sm.step("SYN", bars, i, FAST, blocked) for i in range(255, 263)]
    assert not any(d.watching for d in days)  # every momentum pass was on or before the exit
    fresh = sm.WatchState()
    assert any(sm.step("SYN", bars, i, FAST, fresh).watching for i in range(255, 263))


def test_evidence_records_every_indicator() -> None:
    bars = momentum_stock()
    fired = sm.indicators(bars, FAST)
    ev = sm.evidence(bars, fired, 267, "buy", 3, FAST)
    assert set(ev) == set(sm.INDICATORS)
    assert ev["stocks.ind_candle"]["fired"] and "engulfing" in ev["stocks.ind_candle"]["patterns"]
    assert ev["stocks.ind_candle"]["session"] == bars[267].session_date.isoformat()
    assert not ev["stocks.ind_macd"]["fired"] and ev["stocks.ind_macd"]["values"]["macd"] > 0
    assert ev["stocks.ind_rsi"]["provisional"] and not ev["stocks.ind_macd"]["provisional"]
    today = sm.today_values(bars[:268], sm.indicators(bars[:268], FAST), FAST)
    assert today["buy"]["stocks.ind_pivot"]["fired"]
