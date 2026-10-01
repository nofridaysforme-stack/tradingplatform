"""Fibonacci Pivot Point (spec 07).

Levels are set once per New York trading day (scanner.levels.fib_pivot) and stored as the
`fib_pivot` level set. On each completed 15-minute bar inside the window:
- a close above the upper Break is a long candidate, a close below the lower Break a short
  one (or a touch, with trigger=touch);
- at most max_per_side_per_day signals per side per pair per day;
- stop at the Pivot or the opposite Break; target at Confirmation, Take Profit, or Reset.
Confirmation, Reset, and expiry at the day roll are handled by the signal lifecycle.
"""

from typing import Any

from scanner.indicators.base import Direction
from scanner.strategies.common import (
    Context,
    Evaluation,
    GateOut,
    IndicatorOut,
    Rejection,
    SignalDraft,
    in_window,
    round_price,
    trading_windows,
)

STRATEGY = "fib_pivot"
K = "fib_pivot."
LEVEL_LABELS = {
    "break": "Break",
    "confirmation": "Confirmation",
    "take_profit": "Take Profit",
    "reset": "Reset",
    "pivot": "Pivot",
}


def evaluate(ctx: Context) -> Evaluation:
    out = Evaluation()
    ladder = ctx.levels.get("fib_pivot")
    if not ladder:
        return out
    rules, iid = ctx.rules, ctx.instrument.id
    entry_p = rules.params(K + "entry", iid)
    close = float(ctx.bars.c[ctx.i])
    high, low = float(ctx.bars.h[ctx.i]), float(ctx.bars.l[ctx.i])
    up_break, down_break = float(ladder["up"]["break"]), float(ladder["down"]["break"])
    touch = entry_p["trigger"] == "touch"

    candidates: list[Direction] = []
    if close > up_break or (touch and high >= up_break):
        candidates.append("long")
    if close < down_break or (touch and low <= down_break):
        candidates.append("short")

    for direction in candidates:
        result = _candidate(ctx, ladder, direction)
        if isinstance(result, SignalDraft):
            out.signals.append(result)
        else:
            out.rejections.append(result)
    return out


def _candidate(
    ctx: Context, ladder: dict[str, Any], direction: Direction
) -> SignalDraft | Rejection:
    rules, iid, pip = ctx.rules, ctx.instrument.id, ctx.instrument.pip_size
    gates: list[GateOut] = []
    side, other = ("up", "down") if direction == "long" else ("down", "up")
    entry = float(ctx.bars.c[ctx.i])

    if rules.enabled(K + "window"):
        which = rules.params(K + "window", iid)["window"]
        shared = rules.params("three_eight.trading_window", iid)  # the systems share a schedule
        windows = trading_windows(shared, which)
        gates.append(
            GateOut(
                key=K + "window",
                passed=any(in_window(ctx.bar_close_time, a, b) for a, b in windows),
                detail={"window": which},
            )
        )

    max_per_side = int(rules.params(K + "one_per_side", iid)["max_per_side_per_day"])
    taken = sum(
        1
        for s in ctx.prior_signals
        if s.strategy == STRATEGY and s.direction == direction and s.trading_day == ctx.trading_day
    )
    if rules.enabled(K + "one_per_side"):
        gates.append(
            GateOut(
                key=K + "one_per_side",
                passed=taken < max_per_side,
                detail={"taken": taken, "max": max_per_side},
            )
        )

    stop_at = rules.params(K + "stop", iid)["stop_at"]
    stop = float(ladder["pivot"]) if stop_at == "pivot" else float(ladder[other]["break"])
    target_at = rules.params(K + "target", iid)["target_at"]
    target = float(ladder[side][target_at])
    sign = 1 if direction == "long" else -1
    valid = sign * (entry - stop) > 0 and sign * (target - entry) > 0
    gates.append(
        GateOut(
            key=K + "target",
            passed=valid,
            detail={"stop_at": stop_at, "target_at": target_at}
            | ({} if valid else {"reason": "entry is already beyond the target or stop"}),
        )
    )

    failed = [g.key for g in gates if not g.passed]
    if failed:
        return Rejection(
            strategy=STRATEGY, direction=direction, bar_ts=ctx.bar_ts, failed=failed, gates=gates
        )

    risk = abs(entry - stop) / pip
    reward = abs(target - entry) / pip
    decimals = ctx.instrument.display_decimals
    entry_rule = rules.rule(K + "entry")
    used = [K + n for n in ("entry", "stop", "target", "levels", "unit")]
    dedupe = f"{STRATEGY}:{ctx.instrument.symbol}:{direction}:{ctx.trading_day.isoformat()}"
    if taken:
        dedupe += f":{taken + 1}"
    stop_label = "the Pivot" if stop_at == "pivot" else "the opposite Break"
    return SignalDraft(
        strategy=STRATEGY,
        instrument_id=iid,
        instrument=ctx.instrument.symbol,
        direction=direction,
        bar_ts=ctx.bar_ts,
        trading_day=ctx.trading_day,
        entry=round_price(entry, decimals),
        stop=round_price(stop, decimals),
        target=round_price(target, decimals),
        risk_pips=round(risk, 1),
        reward_pips=round(reward, 1),
        reward_risk=round(reward / risk, 3) if risk else 0.0,
        has_provisional=any(rules.provisional(k) for k in used if rules.has(k)),
        indicators=[
            IndicatorOut(
                key=K + "entry",
                name="Break",
                version=entry_rule.version,
                fired=True,
                counted=False,
                provisional=entry_rule.provisional,
                level_ref=f"fib.{side}.break",
                detail={
                    "level": float(ladder[side]["break"]),
                    "trigger": entry_rule.params["trigger"],
                },
            )
        ],
        gates=gates,
        version_set=rules.version_set(strategy=STRATEGY),
        context={
            "ladder": ladder,
            "stop_at": stop_at,
            "target_at": target_at,
            "confirmation": float(ladder[side]["confirmation"]),
            "reset": float(ladder[side]["reset"]),
        },
        explanation=(
            f"{direction.capitalize()} on a close {'above' if direction == 'long' else 'below'} "
            f"the {'upper' if direction == 'long' else 'lower'} Break at "
            f"{round_price(float(ladder[side]['break']), decimals)}. Stop at {stop_label}, "
            f"target at {LEVEL_LABELS[target_at]}."
        ),
        dedupe_key=dedupe,
    )
