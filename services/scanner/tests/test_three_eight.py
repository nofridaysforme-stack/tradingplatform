from datetime import timedelta
from typing import Any

import pytest

from scanner.rules.registry import RuleSet
from scanner.strategies import three_eight
from scanner.strategies.common import Evaluation, PriorSignal
from tests.conftest import load_fixture, ruleset_from_snapshot
from tests.strategy_kit import FIXED_ID, context

WORKED = load_fixture("eurusd_worked_example.json")


def with_params(key: str, **params: Any) -> RuleSet:
    rs = ruleset_from_snapshot()
    rule = rs.rule(key)
    rules = {k: rs.rule(k) for k in rs._rules}
    rules[key] = rule.model_copy(update={"params": {**rule.params, **params}})
    return RuleSet(rules)


def disabled(key: str) -> RuleSet:
    rs = ruleset_from_snapshot()
    rules = {k: rs.rule(k) for k in rs._rules}
    rules[key] = rules[key].model_copy(update={"enabled": False})
    return RuleSet(rules)


def failed(ev: Evaluation, direction: str = "long") -> list[str]:
    return next(r.failed for r in ev.rejections if r.direction == direction)


def test_worked_example_matches_spec_06() -> None:
    ev = three_eight.evaluate(context(WORKED))
    exp = WORKED["expected"]["signals"][0]
    assert len(ev.signals) == 1
    s = ev.signals[0]
    assert s.direction == exp["direction"]
    assert (s.entry, s.stop, s.target) == (exp["entry"], exp["stop"], exp["target"])
    assert round(s.reward_risk, 2) == exp["reward_risk"]
    assert (s.risk_pips, s.reward_pips) == (exp["risk_pips"], exp["reward_pips"])
    assert [i.key for i in s.indicators if i.fired] == exp["fired"]
    assert s.context["trigger"] == exp["trigger"]
    assert s.explanation == exp["explanation"]
    assert s.dedupe_key == "three_eight:EUR/USD:long:daily.S1:2026-10-05"
    assert s.indicator_count == 3 and s.minimum == 3
    assert not s.has_provisional and not s.is_countertrend and not s.range_mode


def test_payload_lists_all_eight_indicators_and_the_version_set() -> None:
    s = three_eight.evaluate(context(WORKED)).signals[0]
    counting = [
        i for i in s.indicators if i.key in {"three_eight." + n for n in three_eight.INDICATORS[:8]}
    ]
    assert len(counting) == 8
    assert s.version_set["three_eight.target"] == 2
    assert all(k.startswith("three_eight.") for k in s.version_set)
    pivot = next(i for i in s.indicators if i.key == "three_eight.pivot_touch")
    assert pivot.level_ref == "daily.S1" and pivot.detail["distance_pips"] == 6.0
    assert s.context["plan"]["stop_from"] == "daily.S2"
    assert s.context["plan"]["target_from"] == "pdh"


def test_countertrend_fast_move_is_rejected() -> None:
    fx = load_fixture("countertrend_fast_move.json")
    ev = three_eight.evaluate(context(fx))
    assert ev.signals == []
    assert failed(ev, "short") == fx["expected"]["rejected"]["short"]


def test_countertrend_slow_move_is_allowed() -> None:
    ev = three_eight.evaluate(context(load_fixture("countertrend_slow_move.json")))
    assert [(s.direction, s.is_countertrend) for s in ev.signals] == [("short", True)]
    s = ev.signals[0]
    assert s.explanation.endswith("Trend is up. Countertrend trade.")
    assert s.reward_pips == 25.0  # countertrend target capped at 25 pips


@pytest.mark.parametrize("case", load_fixture("econ_window.json")["cases"], ids=lambda c: c["name"])
def test_econ_window(case: dict[str, Any]) -> None:
    fx = load_fixture("econ_window.json")
    ev = three_eight.evaluate(context(fx, case["bars"]))
    shorts = [s for s in ev.signals if s.direction == "short"]
    if case["expected_allowed"]:
        assert shorts and shorts[0].is_countertrend
        econ = next(g for g in shorts[0].gates if g.key == "three_eight.econ")
        assert econ.passed
    else:
        assert not shorts
        assert failed(ev, "short") == ["three_eight.econ"]


def test_econ_window_blocks_fibonacci_targets() -> None:
    fx = load_fixture("econ_window.json")
    s = three_eight.evaluate(context(fx, fx["cases"][0]["bars"])).signals[0]
    assert not str(s.context["plan"]["target_from"]).startswith("fib")


def test_trading_window_gate() -> None:
    rs = with_params("three_eight.trading_window", window="alternative")
    assert failed(three_eight.evaluate(context(WORKED, rules=rs))) == ["three_eight.trading_window"]
    rs = with_params("three_eight.trading_window", window="both")
    assert three_eight.evaluate(context(WORKED, rules=rs)).signals


def test_minimum_indicators_gate() -> None:
    rs = with_params("three_eight.min_indicators", minimum=4)
    assert failed(three_eight.evaluate(context(WORKED, rules=rs))) == ["three_eight.min_indicators"]


def test_disabling_an_indicator_removes_it_from_the_count() -> None:
    ev = three_eight.evaluate(context(WORKED, rules=disabled("three_eight.candlestick")))
    assert failed(ev) == ["three_eight.min_indicators"]


def test_reward_risk_gate() -> None:
    rs = with_params("three_eight.reward_risk", min_ratio=3.0)
    assert failed(three_eight.evaluate(context(WORKED, rules=rs))) == ["three_eight.reward_risk"]


def test_target_minimum_is_a_setting() -> None:
    rs = with_params("three_eight.target", daily_target_min_pips=70)
    assert three_eight.evaluate(context(WORKED, rules=rs)).signals  # shown only by default
    rs = with_params("three_eight.target", daily_target_min_pips=70, reject_below_min=True)
    assert failed(three_eight.evaluate(context(WORKED, rules=rs))) == ["three_eight.reward_risk"]


def test_per_instrument_override_applies() -> None:
    rs = ruleset_from_snapshot()
    rules = {k: rs.rule(k) for k in rs._rules}
    overridden = RuleSet(rules, {("three_eight.target", FIXED_ID): {"daily_target_max_pips": 60}})
    s = three_eight.evaluate(context(WORKED, rules=overridden)).signals[0]
    assert s.target == 1.0894  # R1 (68 pips) is out of reach; P is the furthest within 60


def test_cooldown_blocks_a_second_signal() -> None:
    ctx = context(WORKED)
    prior = [
        PriorSignal("three_eight", "long", ctx.bar_ts - timedelta(minutes=45), ctx.trading_day)
    ]
    ev = three_eight.evaluate(context(WORKED, prior=prior))
    assert failed(ev) == ["three_eight.cooldown"]
    older = [
        PriorSignal("three_eight", "long", ctx.bar_ts - timedelta(minutes=75), ctx.trading_day)
    ]
    assert three_eight.evaluate(context(WORKED, prior=older)).signals
    other_side = [
        PriorSignal("three_eight", "short", ctx.bar_ts - timedelta(minutes=15), ctx.trading_day)
    ]
    assert three_eight.evaluate(context(WORKED, prior=other_side)).signals


def test_daily_goal_suppression_when_switched_on() -> None:
    ctx = context(WORKED)
    won = [
        PriorSignal(
            "three_eight",
            "short",
            ctx.bar_ts - timedelta(hours=3),
            ctx.trading_day,
            closed=True,
            result_pips=62.0,
        )
    ]
    assert three_eight.evaluate(context(WORKED, prior=won)).signals  # off by default
    rs = with_params("three_eight.daily_goal", suppress_after_goal=True)
    assert failed(three_eight.evaluate(context(WORKED, rules=rs, prior=won))) == [
        "three_eight.daily_goal"
    ]


def test_no_trend_and_no_range_is_rejected() -> None:
    rs = with_params("three_eight.swing", threshold_pips=100)  # no swings, so no trend
    ev = three_eight.evaluate(context(WORKED, rules=rs))
    assert "three_eight.trend_alignment" in failed(ev)


def test_only_completed_bars_are_used() -> None:
    """The strategy sees exactly the bars it is given; the last one is the signal bar."""
    ctx = context(WORKED)
    s = three_eight.evaluate(ctx).signals[0]
    assert s.bar_ts == ctx.bars.ts[-1]


def test_range_mode_long_near_the_range_low() -> None:
    fx = load_fixture("range_mode.json")
    [s] = three_eight.evaluate(context(fx)).signals
    assert s.direction == "long" and s.range_mode and not s.is_countertrend
    assert s.context["plan"]["target_from"] == "range edge"
    assert s.explanation.endswith("Market is ranging.")
    off = disabled("three_eight.range_mode")
    assert "three_eight.trend_alignment" in failed(three_eight.evaluate(context(fx, rules=off)))


def test_range_mode_minimum_is_a_setting() -> None:
    fx = load_fixture("range_mode.json")
    rs = with_params("three_eight.range_mode", range_minimum=6)
    assert failed(three_eight.evaluate(context(fx, rules=rs))) == ["three_eight.min_indicators"]


def test_weekly_pivot_countertrend_targets_the_opposite_weekly_pivot() -> None:
    fx = load_fixture("countertrend_slow_move.json")
    levels = {**fx["levels"], "weekly": {"P": 1.0870, "R1": 1.0884, "S1": 1.0850}}
    [s] = three_eight.evaluate(context({**fx, "levels": levels})).signals
    assert s.context["trigger"] == "weekly.R1"
    assert s.context["plan"]["target_from"] == "weekly.S1" and s.target == 1.085
