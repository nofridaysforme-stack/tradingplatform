from datetime import timedelta
from typing import Any

from scanner.rules.registry import RuleSet
from scanner.strategies import fib_pivot
from scanner.strategies.common import PriorSignal
from tests.conftest import load_fixture, ruleset_from_snapshot
from tests.strategy_kit import context

FX = load_fixture("fib_pivot_signal.json")


def with_params(key: str, **params: Any) -> RuleSet:
    rs = ruleset_from_snapshot()
    rules = {k: rs.rule(k) for k in rs._rules}
    rules[key] = rules[key].model_copy(update={"params": {**rules[key].params, **params}})
    return RuleSet(rules)


def test_close_above_upper_break_is_a_long() -> None:
    ev = fib_pivot.evaluate(context(FX))
    exp = FX["expected"]
    assert len(ev.signals) == 1
    s = ev.signals[0]
    assert (s.direction, s.entry, s.stop, s.target) == (
        exp["direction"],
        exp["entry"],
        exp["stop"],
        exp["target"],
    )
    assert (s.risk_pips, s.reward_pips) == (exp["risk_pips"], exp["reward_pips"])
    assert s.dedupe_key == exp["dedupe_key"]
    assert s.has_provisional
    assert s.indicators[0].name == "Break"
    assert s.context["confirmation"] == 1.0959
    assert s.explanation == (
        "Long on a close above the upper Break at 1.0925. Stop at the Pivot, target at Take Profit."
    )


def test_close_below_lower_break_is_a_short() -> None:
    bars = [["2026-10-05T08:00:00+00:00", 1.0818, 1.0820, 1.0805, 1.0810]]
    s = fib_pivot.evaluate(context(FX, bars)).signals[0]
    assert (s.direction, s.stop, s.target) == ("short", 1.087, 1.0726)


def test_no_trigger_inside_the_breaks() -> None:
    bars = [["2026-10-05T08:00:00+00:00", 1.0900, 1.0930, 1.0890, 1.0920]]  # wick only
    assert fib_pivot.evaluate(context(FX, bars)).signals == []
    touch = with_params("fib_pivot.entry", trigger="touch")
    assert fib_pivot.evaluate(context(FX, bars, rules=touch)).signals


def test_stop_and_target_settings() -> None:
    rs = with_params("fib_pivot.stop", stop_at="opposite_break")
    s = fib_pivot.evaluate(context(FX, rules=rs)).signals[0]
    assert s.stop == 1.0815
    rs = with_params("fib_pivot.target", target_at="reset")
    assert fib_pivot.evaluate(context(FX, rules=rs)).signals[0].target == 1.1103


def test_entry_beyond_target_is_rejected() -> None:
    bars = [["2026-10-05T08:00:00+00:00", 1.1010, 1.1030, 1.1005, 1.1020]]
    ev = fib_pivot.evaluate(context(FX, bars))
    assert ev.signals == [] and ev.rejections[0].failed == ["fib_pivot.target"]


def test_one_signal_per_side_per_day() -> None:
    ctx = context(FX)
    prior = [PriorSignal("fib_pivot", "long", ctx.bar_ts - timedelta(hours=1), ctx.trading_day)]
    ev = fib_pivot.evaluate(context(FX, prior=prior))
    assert ev.rejections[0].failed == ["fib_pivot.one_per_side"]
    rs = with_params("fib_pivot.one_per_side", max_per_side_per_day=2)
    s = fib_pivot.evaluate(context(FX, rules=rs, prior=prior)).signals[0]
    assert s.dedupe_key.endswith(":2")


def test_window_gate() -> None:
    late = [["2026-10-05T16:00:00+00:00", 1.0922, 1.0930, 1.0920, 1.0928]]  # 12:15 New York
    ev = fib_pivot.evaluate(context(FX, late))
    assert ev.rejections[0].failed == ["fib_pivot.window"]


def test_no_ladder_no_signal() -> None:
    assert fib_pivot.evaluate(context({**FX, "levels": {}})).signals == []
