"""The stock momentum system (spec 08, revised 2026-10-08 and 2026-10-20)."""

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
OPEN = sm.us_sessions()


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
    """A year rising from 3 to 6, a 64 percent run in 25 sessions (to Friday 2025-01-17), a
    7-session pullback inside the zone, an engulfing bounce, a climb, then a fall."""
    rows, p = [], 3.0
    for k in range(250):
        n = 3 + 3 * (k + 1) / 250
        rows.append((p, n))
        p = n
    for step, count in [(1.02, 25), (0.988, 7)]:
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


def deep_pullback_stock() -> list[DayBar]:
    """momentum_stock up to its last qualifying date (index 274), then a 22 percent fall in
    6 sessions and a 4-session bounce that stays over 10 percent below the high."""
    rows = [(float(b.o or b.c), float(b.c)) for b in momentum_stock()[:275]]
    p = rows[-1][1]
    for step, count in [(0.96, 6), (1.03, 4)]:
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


def test_ten_week_ladder_matches_the_owners_worked_example() -> None:
    """Owners' note of 2026-10-20: Friday close 12.00; a week earlier 11.00 gives
    (12 - 11) / 11 / 5 x 260 = 472 percent, two weeks earlier 10.00 gives 520 percent."""
    values = [11.9] * 60
    values[49], values[54], values[59] = 10.0, 11.0, 12.0  # Fridays 2024-03-08, 15, 22
    bars = closes(values)
    assert bars[59].session_date == date(2024, 3, 22)
    lad = sm.ladder(bars, 59, RULES)
    first, second = lad.rungs[0], lad.rungs[1]
    assert (first.weeks, first.days, first.session, first.close) == (
        1,
        5,
        date(2024, 3, 15),
        D("11"),
    )
    assert round(first.rate or 0, 4) == D("4.7273") and first.passed
    assert (second.days, second.rate, second.passed) == (10, D("5.2"), True)
    assert [r.days for r in lad.rungs] == [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    assert lad.passes == 2 and not lad.passed  # needs 5 of the 10
    assert sm.ladder(bars, 59, derive(RULES, {"stocks.momentum": {"min_weeks_passing": 2}})).passed


def test_momentum_is_tested_on_the_weeks_close_only() -> None:
    values = [11.9] * 60
    values[58] = values[59] = 30.0  # every week back passes
    bars = closes(values)
    assert sm.ladder(bars, 59, RULES).passes == 10
    assert sm.passes_momentum(bars, RULES, OPEN)  # Friday 2024-03-22
    thursday = bars[:59]
    assert sm.ladder(thursday, 58, RULES).passed
    assert not sm.passes_momentum(thursday, RULES, OPEN)
    off = derive(RULES, disabled={"stocks.momentum"})
    assert sm.passes_momentum(thursday, off, OPEN)  # switched off: every session passes


def test_a_closed_friday_makes_thursday_the_weeks_close() -> None:
    """Good Friday 2026-04-03: the Thursday close stands in (owners 2026-10-20)."""
    assert sm.is_week_close(date(2026, 4, 2), OPEN)
    assert not sm.is_week_close(date(2026, 4, 1), OPEN)
    assert not sm.is_week_close(date(2026, 4, 9), OPEN) and sm.is_week_close(
        date(2026, 4, 10), OPEN
    )
    closed = sm.us_sessions({date(2026, 10, 16)})  # an unscheduled closure from market_holidays
    assert sm.is_week_close(date(2026, 10, 15), closed)
    days = [date(2026, 3, 30) + timedelta(days=k) for k in range(12)]
    sessions = [d for d in days if OPEN(d)]
    bars = [DayBar(d, D(10), D(10), D(10), 500_000, D(10)) for d in sessions]
    assert bars[-1].session_date == date(2026, 4, 10)
    k = sm.week_close_back(bars, len(bars) - 1, 1)
    assert k is not None and bars[k].session_date == date(2026, 4, 2)


def test_a_qualifying_date_keeps_the_stock_watched_for_60_sessions() -> None:
    """After its last pass (Friday 2025-01-17, index 274) the stock stays on the watch list
    for 60 sessions, about 3 months, through a drop below the pullback zone (owners
    2026-10-20 and 2026-10-29)."""
    bars = momentum_stock()[:275]
    top = bars[-1]
    for k in range(65):
        d = bars[-1].session_date + timedelta(days=3 if bars[-1].session_date.weekday() == 4 else 1)
        c = top.c * D("0.8") if 10 <= k < 15 else top.c  # 20 percent below for 5 sessions
        bars.append(DayBar(d, top.h if c == top.c else c, c, c, top.volume, c))
    state = sm.WatchState()
    days = {i: sm.step("SYN", bars, i, RULES, state, OPEN) for i in range(249, len(bars))}
    assert [i for i, d in days.items() if d.momentum] == [269, 274]
    dropped = [i for i, d in days.items() if i > 274 and d.result is None]
    assert dropped == list(range(285, 290))
    assert all(days[i].watching for i in dropped)
    assert [i for i, d in days.items() if d.joined] == [269]  # never rejoins after the drop
    assert days[274 + 59].watching and not days[274 + 60].watching


def test_the_funnel_buys_after_the_pullback_and_sells_on_the_vote() -> None:
    bars = momentum_stock()
    fired = sm.indicators(bars, FAST)
    state = sm.WatchState()
    days = {i: sm.step("SYN", bars, i, FAST, state, OPEN) for i in range(249, 303)}
    # Friday 2025-01-10 (269) is the first week close with 5 of 10 weeks at 455 percent.
    assert [i for i, d in days.items() if d.joined] == [269]
    assert [i for i, d in days.items() if d.momentum] == [269, 274]  # Fridays only
    assert days[264].result is not None and not days[264].momentum  # 4 of 10
    assert days[278].watching and days[278].qualifying == bars[274].session_date
    # Below the pullback zone the stock no longer qualifies, but it stays watched (owners
    # 2026-10-20) and cannot be bought there.
    assert days[299].result is None and days[299].watching
    assert not sm.is_buy(bars, fired, days[299], FAST)
    # The first buy is 282; the votes stay in the window for two more sessions, but by then
    # the stock is held (the replay below opens one position).
    assert next(i for i in range(270, 299) if sm.is_buy(bars, fired, days[i], FAST)) == 282
    votes = {v.key for v in sm.buy_votes(bars, fired, 282, FAST)}
    assert votes == {"stocks.ind_candle", "stocks.ind_pivot", "stocks.ind_rsi", "stocks.ind_stoch"}
    candle = fired["stocks.ind_candle"]
    assert candle.buy[282] and not candle.buy[281]  # the bounce closes above the previous high

    trades, joins = replay("SYN", bars, FAST, OPEN)
    assert joins == 1
    (t,) = trades
    assert (t.buy_session, t.entry, t.reason, t.sessions) == (
        bars[282].session_date, D("9.2721"), "sold", 13,
    )  # fmt: skip
    assert t.exit_price == D("10.8087")
    assert round(float(t.result_pct or 0), 4) == 0.1657
    assert t.has_provisional  # RSI and the candle list are provisional


def test_default_oscillators_rarely_vote_in_a_shallow_pullback() -> None:
    """Spec 08 note: in a pullback of under 10 percent, RSI(14) stays far above 30 and
    Stochastics(14) far above 20, so a buy usually comes from the other three indicators."""
    bars = momentum_stock()
    fired = sm.indicators(bars, RULES)
    assert not fired["stocks.ind_rsi"].buy[270:290].any()
    assert not fired["stocks.ind_stoch"].buy[270:290].any()
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


def test_change_in_direction_candle() -> None:
    """Owners 2026-10-29: the change in direction candle is a close higher than the previous
    session's high. The sell mirror is a close lower than the previous session's low."""
    bars = [
        DayBar(date(2026, 10, 26), D("10.40"), D("10.00"), D("10.20"), 500_000, D("10.10")),
        DayBar(date(2026, 10, 27), D("10.60"), D("10.30"), D("10.55"), 500_000, D("10.30")),
        DayBar(date(2026, 10, 28), D("10.70"), D("10.35"), D("10.60"), 500_000, D("10.50")),
        DayBar(date(2026, 10, 29), D("10.50"), D("10.10"), D("10.20"), 500_000, D("10.50")),
    ]
    f = sm.candle(bars, {})
    # 10.55 is above 10.40; 10.60 is not above 10.60; 10.20 is below the previous low of 10.35.
    assert f.buy.tolist() == [False, True, False, False]
    assert f.sell.tolist() == [False, False, False, True]
    assert (f.values["previous_high"][1], f.values["close"][1]) == (10.40, 10.55)


def test_a_watched_stock_can_be_bought_below_the_pullback_zone() -> None:
    """Owners 2026-10-29: no pullback zone check on the buy. After its last qualifying date
    the stock falls 22 percent below the high, then bounces; the bounce buys at 17 percent
    below the high, where it does not qualify."""
    bars = deep_pullback_stock()
    fired = sm.indicators(bars, FAST)
    state = sm.WatchState()
    days = {i: sm.step("SYN", bars, i, FAST, state, OPEN) for i in range(249, len(bars))}
    assert days[282].result is None and days[282].watching
    assert next(i for i in range(275, len(bars)) if sm.is_buy(bars, fired, days[i], FAST)) == 282
    (t,) = replay("SYN", bars, FAST, OPEN)[0]
    assert (t.buy_session, t.entry) == (bars[282].session_date, D("8.1744"))


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
    blocked = sm.WatchState(blocked_through=274)
    days = [sm.step("SYN", bars, i, FAST, blocked, OPEN) for i in range(260, 278)]
    assert not any(d.watching for d in days)  # every momentum pass was on or before the exit
    fresh = sm.WatchState()
    assert any(sm.step("SYN", bars, i, FAST, fresh, OPEN).watching for i in range(260, 278))


def test_evidence_records_every_indicator() -> None:
    bars = momentum_stock()
    fired = sm.indicators(bars, FAST)
    ev = sm.evidence(bars, fired, 282, "buy", 3, FAST)
    assert set(ev) == set(sm.INDICATORS)
    assert ev["stocks.ind_candle"]["fired"]
    candle = ev["stocks.ind_candle"]["values"]
    assert candle["close"] == 9.2721 and candle["close"] > candle["previous_high"]
    assert ev["stocks.ind_candle"]["session"] == bars[282].session_date.isoformat()
    assert not ev["stocks.ind_macd"]["fired"] and ev["stocks.ind_macd"]["values"]["macd"] > 0
    assert ev["stocks.ind_rsi"]["provisional"] and not ev["stocks.ind_macd"]["provisional"]
    today = sm.today_values(bars[:283], sm.indicators(bars[:283], FAST), FAST, OPEN)
    assert today["buy"]["stocks.ind_pivot"]["fired"]
    mom = today["momentum"]
    # A Wednesday: the ladder shown is the one from the last week close, Friday 2025-01-24.
    assert (mom["week_close"], mom["today"], mom["threshold"]) == ("2025-01-24", False, 4.55)
    assert (mom["needed"], mom["passes"], mom["passed"]) == (5, 1, False)
    assert [w["days"] for w in mom["weeks"]] == [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    friday = sm.momentum_evidence(bars[:275], FAST, OPEN)
    assert friday["today"] and friday["passes"] == 7 and friday["passed"]
    assert friday["weeks"][0]["session"] == bars[269].session_date.isoformat()
