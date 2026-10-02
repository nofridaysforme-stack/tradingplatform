"""The 3/8 Formula (spec 06).

For each completed 15-minute bar:
1. Build context: swings, trend, last leg, range state, econ window.
2. Run every enabled indicator. A candidate exists only where the pivot or Fibonacci
   indicator fires (the trigger); at most one long and one short candidate per bar, each
   from its nearest fired trigger level (decision A23).
3. Check every gate, then let the planner build entry, stop, and target.
4. A candidate that passes every gate becomes a signal that explains itself.

Every number comes from the rules registry. Interpretations not settled by the documents
are listed in docs/specs/20-assumptions-and-open-items.md.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from scanner.indicators.base import Direction, Hit, pips
from scanner.indicators.candles import candlestick_hits
from scanner.indicators.fibonacci import fibonacci_hits, retracements
from scanner.indicators.hl_failure import hl_failure_hits
from scanner.indicators.levels import PIVOT_NAMES, pivot_hits, prev_day_hit
from scanner.indicators.patterns import flag_hits
from scanner.indicators.ranging import RangeState, range_state
from scanner.indicators.swings import Leg, Swing, last_leg, last_swing, zigzag
from scanner.indicators.thrust import hook_reversal_hits, thrust_hits
from scanner.indicators.trend import Trend, trend_state
from scanner.indicators.trendlines import trendline_hits
from scanner.strategies.common import (
    BAR,
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
from scanner.time import to_new_york

STRATEGY = "three_eight"
K = "three_eight."

# The eight indicators in document order, then the two supplementary ones.
INDICATORS = [
    "candlestick",
    "hl_failure",
    "pivot_touch",
    "flag_pennant_triangle",
    "trendline_channel",
    "pdh",
    "pdl",
    "fibonacci",
    "thrust_candle",
    "hook_reversal",
]
TRIGGERS = ("pivot_touch", "fibonacci")


@dataclass
class State:
    """Market context shared by every candidate on this bar."""

    swings: list[Swing]
    trend: Trend
    leg: Leg | None
    range: RangeState | None
    ranging: bool
    econ_events: list[dict[str, Any]]
    hits: dict[str, list[Hit]] = field(default_factory=dict)


@dataclass
class Plan:
    ok: bool
    reason: str = ""
    entry: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    alt_target: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)


def evaluate(ctx: Context) -> Evaluation:
    rules = ctx.rules
    iid = ctx.instrument.id
    pip = ctx.instrument.pip_size
    bars, i = ctx.bars, ctx.i

    def p(name: str) -> dict[str, Any]:
        return rules.params(K + name, iid)

    def on(name: str) -> bool:
        return rules.enabled(K + name)

    swings = zigzag(bars, float(p("swing")["threshold_pips"]) * pip)
    rng: RangeState | None = None
    if on("range_detect"):
        rp = p("range_detect")
        rng = range_state(
            bars,
            i,
            int(rp["lookback_bars"]),
            int(rp["min_retests"]),
            float(rp["retest_tolerance_pips"]),
            float(rp["min_width_pips"]),
            pip,
        )
    state = State(
        swings=swings,
        trend=trend_state(swings),
        leg=last_leg(swings),
        range=rng,
        ranging=bool(rng and rng.ranging and on("range_mode")),
        econ_events=_econ_in_window(ctx, p("econ")) if on("econ") else [],
    )
    state.hits = _indicator_hits(ctx, state, only=TRIGGERS)
    if not any(state.hits.get(name) for name in TRIGGERS):
        return Evaluation()  # no trigger level touched: no candidate can form
    state.hits.update(_indicator_hits(ctx, state, skip=TRIGGERS))

    out = Evaluation()
    directions: tuple[Direction, Direction] = ("long", "short")
    for direction in directions:
        trigger = _trigger(state, direction)
        if trigger is None:
            continue
        result = _candidate(ctx, state, direction, trigger)
        if isinstance(result, SignalDraft):
            out.signals.append(result)
        else:
            out.rejections.append(result)
    return out


# Indicators


def _indicator_hits(
    ctx: Context, state: State, only: tuple[str, ...] = (), skip: tuple[str, ...] = ()
) -> dict[str, list[Hit]]:
    rules, iid, pip = ctx.rules, ctx.instrument.id, ctx.instrument.pip_size
    bars, i, lv = ctx.bars, ctx.i, ctx.levels
    hits: dict[str, list[Hit]] = {}
    for name in INDICATORS:
        key = K + name
        if not rules.enabled(key) or (only and name not in only) or name in skip:
            continue
        p = rules.params(key, iid)
        if name == "candlestick":
            h = candlestick_hits(
                bars, i, p["patterns"], int(p["lookback_bars"]), float(p["shaved_max_shadow_pct"])
            )
        elif name == "hl_failure":
            h = hl_failure_hits(bars, i, state.swings, float(p["test_tolerance_pips"]), pip)
        elif name == "pivot_touch":
            pivots: dict[str, dict[str, float]] = {
                s: lv[s] for s in ("daily", "weekly", "monthly") if s in lv
            }
            tols = {s: float(p[f"{s}_tolerance_pips"]) for s in ("daily", "weekly", "monthly")}
            h = pivot_hits(bars, i, pivots, tols, float(p["double_pivot_pips"]), pip)
        elif name == "flag_pennant_triangle":
            h = flag_hits(
                bars,
                i,
                float(p["pole_min_pips"]),
                int(p["pole_max_bars"]),
                int(p["cons_min_bars"]),
                int(p["cons_max_bars"]),
                pip,
            )
        elif name == "trendline_channel":
            h = trendline_hits(
                bars,
                i,
                state.swings,
                int(p["min_touches"]),
                float(p["touch_tolerance_pips"]),
                float(p["parallel_tolerance_pct"]),
                int(p["max_line_age_bars"]),
                pip,
            )
        elif name == "pdh":
            h = prev_day_hit(
                bars, i, _get(lv, "prev_day", "PDH"), "pdh", float(p["tolerance_pips"]), pip
            )
        elif name == "pdl":
            h = prev_day_hit(
                bars, i, _get(lv, "prev_day", "PDL"), "pdl", float(p["tolerance_pips"]), pip
            )
        elif name == "fibonacci":
            h = fibonacci_hits(bars, i, state.leg, float(p["tolerance_pips"]), p["ratio_set"], pip)
        elif name == "thrust_candle":
            h = thrust_hits(bars, i, float(p["min_body_pips"]), pip)
        else:  # hook_reversal
            h = hook_reversal_hits(bars, i, state.swings, float(p["min_leg_pips"]), pip)
        hits[name] = h
    return hits


def _get(levels: dict[str, dict[str, Any]], kind: str, name: str) -> float | None:
    value = levels.get(kind, {}).get(name)
    return float(value) if value is not None else None


def _trigger(state: State, direction: Direction) -> Hit | None:
    """The trigger level for this direction. Trades trigger off pivots, with Fibonacci as the
    only exception (A4): the nearest fired pivot, or the nearest Fibonacci level when no
    pivot fired (A23)."""
    for name in TRIGGERS:  # pivots first
        candidates = [h for h in state.hits.get(name, []) if h.supports(direction)]
        if candidates:
            return min(candidates, key=lambda h: (h.distance_pips or 0.0, h.level_ref or ""))
    return None


# One candidate


def _candidate(
    ctx: Context, state: State, direction: Direction, trigger: Hit
) -> SignalDraft | Rejection:
    rules, iid, pip = ctx.rules, ctx.instrument.id, ctx.instrument.pip_size
    close = float(ctx.bars.c[ctx.i])
    gates: list[GateOut] = []

    def p(name: str) -> dict[str, Any]:
        return rules.params(K + name, iid)

    def gate(name: str, passed: bool, **detail: object) -> None:
        if rules.enabled(K + name):
            gates.append(GateOut(key=K + name, passed=passed, detail=detail))

    # Indicators in this direction
    indicators: list[IndicatorOut] = []
    count = 0
    fired_names: list[str] = []
    provisional_fired = False
    for name in INDICATORS:
        key = K + name
        if not rules.has(key):
            continue
        rule = rules.rule(key)
        hits = [h for h in state.hits.get(name, []) if h.supports(direction)]
        best: Hit | None
        if (
            name in TRIGGERS
            and trigger.level_ref
            and any(h.level_ref == trigger.level_ref for h in hits)
        ):
            best = trigger
        else:
            best = min(hits, key=lambda h: h.distance_pips or 0.0) if hits else None
        fired = best is not None and rule.enabled
        counted = fired and rule.counts_toward_minimum
        count += counted
        if fired:
            fired_names.append(name)
            provisional_fired = provisional_fired or rule.provisional
        indicators.append(
            IndicatorOut(
                key=key,
                name=rule.name,
                version=rule.version,
                fired=fired,
                counted=counted,
                provisional=rule.provisional,
                level_ref=best.level_ref if fired and best else None,
                detail=_indicator_detail(best) if fired and best else {},
            )
        )

    # Trading window
    tw = p("trading_window")
    windows = trading_windows(tw, tw["window"])
    close_time = ctx.bar_close_time
    gate(
        "trading_window",
        any(in_window(close_time, a, b) for a, b in windows),
        window=tw["window"],
        ny_time=_ny_hhmm(close_time),
    )

    # Trend, countertrend, range mode, econ
    with_trend = (direction == "long" and state.trend == "up") or (
        direction == "short" and state.trend == "down"
    )
    range_mode = False
    countertrend = False
    trend_ok = True
    trend_detail: dict[str, Any] = {"trend": state.trend}
    in_econ = bool(state.econ_events)
    if with_trend:
        pass
    elif state.ranging:
        range_mode = True
        countertrend = state.trend != "none"
    elif state.trend == "none":
        trend_ok = False
        trend_detail["reason"] = "no trend and no range"
    else:
        countertrend = True
        if _new_trend_after_consolidation(ctx, direction):
            countertrend = False
            trend_detail["new_trend"] = True
    gate("trend_alignment", trend_ok or countertrend or range_mode, **trend_detail)

    econ_reversal = False
    if countertrend and not range_mode:
        if in_econ and rules.enabled(K + "econ"):
            ep = p("econ")
            large = _large_bar_since(ctx, state.econ_events, float(ep["large_bar_pips"]))
            econ_reversal = large is not None and "candlestick" in fired_names
            gate(
                "econ",
                large is not None,
                events=state.econ_events,
                large_bar_pips=large,
                min_pips=ep["large_bar_pips"],
            )
        elif rules.enabled(K + "countertrend"):
            ok, detail = _countertrend_allowed(ctx, state, direction)
            gate("countertrend", ok, **detail)
        else:
            gates.append(
                GateOut(key=K + "countertrend", passed=False, detail={"reason": "disabled"})
            )
    elif in_econ and rules.enabled(K + "econ"):
        gate("econ", True, events=state.econ_events)

    # Range mode position
    if range_mode and state.range is not None:
        mid = (state.range.high + state.range.low) / 2
        level = trigger.level if trigger.level is not None else close
        inside = state.range.low <= close <= state.range.high
        right_half = level <= mid if direction == "long" else level >= mid
        gate("range_mode", inside and right_half, high=state.range.high, low=state.range.low)

    # Minimum indicators
    minimum = (
        int(p("range_mode")["range_minimum"]) if range_mode else int(p("min_indicators")["minimum"])
    )
    gate("min_indicators", count >= minimum, count=count, minimum=minimum)

    # Cooldown and daily goal
    if rules.enabled(K + "cooldown"):
        bars_gap = int(p("cooldown")["bars"])
        recent = [
            s
            for s in ctx.prior_signals
            if s.strategy == STRATEGY
            and s.direction == direction
            and timedelta(0) <= ctx.bar_ts - s.bar_ts <= BAR * bars_gap
        ]
        gate("cooldown", not recent, bars=bars_gap)
    if rules.enabled(K + "daily_goal"):
        dg = p("daily_goal")
        if dg["suppress_after_goal"]:
            today = sum(
                s.result_pips or 0.0
                for s in ctx.prior_signals
                if s.strategy == STRATEGY and s.closed and s.trading_day == ctx.trading_day
            )
            gate("daily_goal", today < float(dg["goal_min_pips"]), pips_today=round(today, 1))

    # Planner
    plan = _plan(ctx, state, direction, trigger, countertrend, range_mode, in_econ, econ_reversal)
    gate("stop_feasible", plan.ok or plan.reason.startswith("target"), **_stop_detail(plan))
    risk = abs(plan.entry - plan.stop) / pip if plan.ok else 0.0
    reward = abs(plan.target - plan.entry) / pip if plan.ok else 0.0
    ratio = reward / risk if risk > 0 else 0.0
    min_ratio = float(p("reward_risk")["min_ratio"])
    if plan.ok:
        gate("reward_risk", ratio + 1e-9 >= min_ratio, ratio=round(ratio, 2), min=min_ratio)
    else:
        gates.append(GateOut(key=K + "reward_risk", passed=False, detail={"reason": plan.reason}))

    failed = [g.key for g in gates if not g.passed]
    if failed:
        return Rejection(
            strategy=STRATEGY, direction=direction, bar_ts=ctx.bar_ts, failed=failed, gates=gates
        )

    decimals = ctx.instrument.display_decimals
    return SignalDraft(
        strategy=STRATEGY,
        instrument_id=iid,
        instrument=ctx.instrument.symbol,
        direction=direction,
        bar_ts=ctx.bar_ts,
        trading_day=ctx.trading_day,
        entry=round_price(plan.entry, decimals),
        stop=round_price(plan.stop, decimals),
        target=round_price(plan.target, decimals),
        alt_target=round_price(plan.alt_target, decimals) if plan.alt_target else None,
        risk_pips=round(risk, 1),
        reward_pips=round(reward, 1),
        reward_risk=round(ratio, 3),
        indicator_count=count,
        minimum=minimum,
        has_provisional=provisional_fired,
        is_countertrend=countertrend,
        range_mode=range_mode,
        indicators=indicators,
        gates=gates,
        version_set=rules.version_set(strategy=STRATEGY),
        context={
            "trend": state.trend,
            "trigger": trigger.level_ref,
            "leg": [state.leg.start.price, state.leg.end.price] if state.leg else None,
            "range": state.range.__dict__ if state.range and range_mode else None,
            "plan": plan.detail,
        },
        explanation=_explain(direction, trigger, indicators, state.trend, countertrend, range_mode),
        dedupe_key=f"{STRATEGY}:{ctx.instrument.symbol}:{direction}:{trigger.level_ref}:{ctx.trading_day.isoformat()}",
    )


def _indicator_detail(hit: Hit) -> dict[str, Any]:
    detail = dict(hit.detail)
    if hit.level is not None:
        detail.setdefault("level", hit.level)
    if hit.distance_pips is not None:
        detail.setdefault("distance_pips", hit.distance_pips)
    return detail


def _ny_hhmm(ts: datetime) -> str:
    return to_new_york(ts).strftime("%H:%M")


# Countertrend and econ


def _countertrend_allowed(
    ctx: Context, state: State, direction: Direction
) -> tuple[bool, dict[str, Any]]:
    """Rule three_eight.countertrend (a) and (b). (c) is handled by the caller."""
    p = ctx.rules.params(K + "countertrend", ctx.instrument.id)
    pip = ctx.instrument.pip_size
    bars, i = ctx.bars, ctx.i
    trend_up = state.trend == "up"
    anchor = last_swing(state.swings, "low" if trend_up else "high")
    if anchor is None:
        return False, {"reason": "no opposite swing"}
    seg = slice(anchor.index, i + 1)
    if trend_up:
        move = float(bars.h[seg].max()) - anchor.price
    else:
        move = anchor.price - float(bars.l[seg].min())
    move_pips = pips(move, pip)
    fast = _fastest_move(ctx, anchor.index, trend_up, int(p["fast_move_bars"]))
    detail = {
        "move_pips": round(move_pips, 1),
        "min_move_pips": p["min_move_pips"],
        "fastest_move_pips": round(fast, 1),
        "fast_move_bars": p["fast_move_bars"],
    }
    if move_pips + 1e-9 < float(p["min_move_pips"]):
        return False, {**detail, "reason": "move too small"}
    if fast + 1e-9 >= float(p["fast_move_pips"]):
        return False, {**detail, "reason": "move too fast"}
    return True, detail


def _fastest_move(ctx: Context, start: int, up: bool, window: int) -> float:
    """Largest move in the trend direction inside any run of `window` bars since start."""
    bars, i, pip = ctx.bars, ctx.i, ctx.instrument.pip_size
    best = 0.0
    for end in range(start, i + 1):
        lo = max(start, end - window + 1)
        if up:
            best = max(best, float(bars.h[end]) - float(bars.l[lo : end + 1].min()))
        else:
            best = max(best, float(bars.h[lo : end + 1].max()) - float(bars.l[end]))
    return pips(best, pip)


def _new_trend_after_consolidation(ctx: Context, direction: Direction) -> bool:
    """Rule three_eight.countertrend (c): after a consolidation of new_trend_consolidation_hours
    that resolves in the candidate's direction, the move is a new trend, not a countertrend."""
    rules, iid = ctx.rules, ctx.instrument.id
    if not (rules.enabled(K + "countertrend") and rules.enabled(K + "range_detect")):
        return False
    hours = float(rules.params(K + "countertrend", iid)["new_trend_consolidation_hours"])
    lookback = int(hours * 4)
    if ctx.i - 1 < lookback:
        return False
    rp = rules.params(K + "range_detect", iid)
    prior = range_state(
        ctx.bars,
        ctx.i - 1,
        lookback,
        int(rp["min_retests"]),
        float(rp["retest_tolerance_pips"]),
        float(rp["min_width_pips"]),
        ctx.instrument.pip_size,
    )
    if not prior.ranging:
        return False
    close = float(ctx.bars.c[ctx.i])
    return close > prior.high if direction == "long" else close < prior.low


def _econ_in_window(ctx: Context, p: dict[str, Any]) -> list[dict[str, Any]]:
    window = timedelta(minutes=float(p["window_minutes"]))
    close_time = ctx.bar_close_time
    currencies = set(ctx.instrument.currencies)
    return [
        {"at": e.at.isoformat(), "currency": e.currency}
        for e in ctx.econ_events
        if e.impact == "high" and e.currency in currencies and e.at <= close_time <= e.at + window
    ]


def _large_bar_since(ctx: Context, events: list[dict[str, Any]], min_pips: float) -> float | None:
    """Largest single 15-minute bar (high to low) since the earliest event in the window."""
    first = min(datetime.fromisoformat(e["at"]) for e in events)
    bars, pip = ctx.bars, ctx.instrument.pip_size
    sizes = [
        pips(float(bars.h[k] - bars.l[k]), pip)
        for k in range(len(bars))
        if bars.ts[k] + BAR > first
    ]
    biggest = max(sizes, default=0.0)
    return round(biggest, 1) if biggest + 1e-9 >= min_pips else None


# Planner


def _daily_pivots(ctx: Context) -> dict[str, float]:
    daily = ctx.levels.get("daily", {})
    return {n: float(daily[n]) for n in PIVOT_NAMES if n in daily}


def _plan(
    ctx: Context,
    state: State,
    direction: Direction,
    trigger: Hit,
    countertrend: bool,
    range_mode: bool,
    in_econ: bool,
    econ_reversal: bool,
) -> Plan:
    rules, iid, pip = ctx.rules, ctx.instrument.id, ctx.instrument.pip_size
    entry = float(ctx.bars.c[ctx.i])
    sign = 1.0 if direction == "long" else -1.0
    pivots = _daily_pivots(ctx)  # decision A20: daily pivots only for stop and target

    # Stop
    sp = rules.params(K + "stop", iid)
    buffer = float(sp["buffer_pips"]) * pip
    stop: float | None = None
    stop_detail: dict[str, Any] = {}
    relaxed: tuple[float, dict[str, Any]] | None = None  # beyond the maximum (econ reversal)
    if (trigger.level_ref or "").split(".")[0] in ("daily", "weekly", "monthly"):
        beyond = sorted(
            (
                (n, v)
                for n, v in pivots.items()
                if (v < entry if direction == "long" else v > entry)
            ),
            key=lambda nv: abs(entry - nv[1]),
        )
        for name, level in beyond:
            candidate = level - sign * buffer
            dist = abs(entry - candidate) / pip
            if dist + 1e-9 < float(sp["pivot_stop_min_pips"]):
                continue
            detail = {"stop_from": f"daily.{name}", "distance_pips": round(dist, 1)}
            if dist <= float(sp["pivot_stop_max_pips"]) + 1e-9:
                stop, stop_detail = candidate, detail
            else:
                relaxed = (candidate, {**detail, "beyond_maximum": True})
            break
    if stop is None:
        swing = last_swing(state.swings, "low" if direction == "long" else "high")
        if swing is not None:
            raw = abs(entry - (swing.price - sign * buffer)) / pip
            clears = (swing.price < entry) if direction == "long" else (swing.price > entry)
            dist = max(raw if clears else 0.0, float(sp["fallback_min_pips"]))
            detail = {
                "stop_from": f"swing.{swing.kind}",
                "swing": swing.price,
                "distance_pips": round(dist, 1),
            }
            if dist <= float(sp["fallback_max_pips"]) + 1e-9:
                stop, stop_detail = entry - sign * dist * pip, detail
            elif relaxed is None:
                relaxed = (entry - sign * dist * pip, {**detail, "beyond_maximum": True})
    if stop is None and econ_reversal and relaxed is not None:
        # Econ rule: a large move followed by a reversing candle is allowed regardless of
        # stop distance.
        stop, stop_detail = relaxed
    if stop is None:
        return Plan(False, "stop: no stop within the allowed distance", entry)

    # Target
    tp = rules.params(K + "target", iid)
    target: float | None = None
    target_detail: dict[str, Any] = {}
    ahead = {n: v for n, v in pivots.items() if (v > entry if direction == "long" else v < entry)}
    if countertrend:
        cap = float(tp["countertrend_target_max_pips"]) * pip
        trig = trigger.level_ref or ""
        if trig.startswith("weekly.") and trig.split(".")[1] != "P":
            opposite = {"S": "R", "R": "S"}[trig.split(".")[1][0]] + trig.split(".")[1][1:]
            weekly = ctx.levels.get("weekly", {})
            if opposite in weekly:
                target = float(weekly[opposite])
                target_detail = {
                    "target_from": f"weekly.{opposite}",
                    "rule": "weekly pivot exception",
                }
        if target is None:
            fib_levels = (
                []
                if (in_econ or state.leg is None)
                else [
                    (ref, v)
                    for ref, v in retracements(
                        state.leg, rules.params(K + "fibonacci", iid)["ratio_set"]
                    ).items()
                    if (v > entry if direction == "long" else v < entry)
                ]
            )
            nearest = sorted(
                fib_levels or [(f"daily.{n}", v) for n, v in ahead.items()],
                key=lambda rv: abs(rv[1] - entry),
            )
            if nearest:
                ref, level = nearest[0]
                capped = abs(level - entry) > cap
                target = entry + sign * cap if capped else level
                target_detail = {"target_from": ref, "capped": capped}
        min_pips = float(tp["countertrend_target_min_pips"])
    else:
        within = {
            n: v
            for n, v in ahead.items()
            if abs(v - entry) / pip <= float(tp["daily_target_max_pips"]) + 1e-9
        }
        if within:
            name, level = max(within.items(), key=lambda nv: abs(nv[1] - entry))
            target, target_detail = level, {"target_from": f"daily.{name}"}
            cap_ref = "PDH" if direction == "long" else "PDL"
            cap_level = _get(ctx.levels, "prev_day", cap_ref)
            if cap_level is not None and min(entry, level) < cap_level < max(entry, level):
                target, target_detail = (
                    cap_level,
                    {"target_from": cap_ref.lower(), "capped_from": f"daily.{name}"},
                )
        min_pips = float(tp["daily_target_min_pips"])
    if range_mode and state.range is not None:
        edge = state.range.high if direction == "long" else state.range.low
        if target is None or (target > edge if direction == "long" else target < edge):
            target, target_detail = edge, {"target_from": "range edge"}
    if target is None:
        return Plan(False, "target: no level within reach", entry, stop, detail=stop_detail)
    distance = abs(target - entry) / pip
    target_detail["distance_pips"] = round(distance, 1)
    if tp.get("reject_below_min") and distance + 1e-9 < min_pips:
        return Plan(
            False,
            f"target: {round(distance, 1)} pips is below the {min_pips} pip minimum",
            entry,
            stop,
            target,
            detail={**stop_detail, **target_detail},
        )

    alt = None
    for h in state.hits.get("flag_pennant_triangle", []):
        if h.supports(direction):
            alt = float(h.detail["projected_target"])
    return Plan(True, "", entry, stop, target, alt, {**stop_detail, **target_detail})


def _stop_detail(plan: Plan) -> dict[str, Any]:
    if plan.ok:
        return {k: v for k, v in plan.detail.items() if k.startswith("stop") or k == "swing"}
    return {"reason": plan.reason}


# Explanation (template-built, deterministic)


def _phrase(ind: IndicatorOut) -> str:
    ref = ind.level_ref or ""
    key = ind.key.removeprefix(K)
    if key == "pivot_touch":
        set_name, name = ref.split(".")
        return f"{set_name} {name}"
    if key == "fibonacci":
        return f"the {ref.removeprefix('fib.').removesuffix('.0')}% retracement"
    if key == "pdh":
        return "the previous day's high"
    if key == "pdl":
        return "the previous day's low"
    if key == "candlestick":
        pattern = str(ind.detail.get("pattern", "candle"))
        if "(" in pattern:
            name, side = pattern.rstrip(")").split(" (")
            return f"a {side} {name.lower()} candle"
        return f"a {pattern.lower()} candle"
    if key == "hl_failure":
        return "a failed test of the swing " + ("low" if ref.endswith("low") else "high")
    if key == "flag_pennant_triangle":
        return "a " + str(ind.detail.get("pattern", "pattern")).lower() + " breakout"
    if key == "trendline_channel":
        return f"trendline {ind.detail.get('side', '')}".strip()
    if key == "thrust_candle":
        return "a thrust candle"
    return "a hook reversal"


def _join(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _explain(
    direction: Direction,
    trigger: Hit,
    indicators: list[IndicatorOut],
    trend: Trend,
    countertrend: bool,
    range_mode: bool,
) -> str:
    fired = [ind for ind in indicators if ind.fired]
    trigger_ind = next(
        (
            ind
            for ind in fired
            if ind.key.removeprefix(K) in TRIGGERS and ind.level_ref == trigger.level_ref
        ),
        None,
    )
    rest = [_phrase(ind) for ind in fired if ind is not trigger_ind]
    head = (
        f"{direction.capitalize()} at {_phrase(trigger_ind)}"
        if trigger_ind
        else direction.capitalize()
    )
    sentence = f"{head} with {_join(rest)}." if rest else f"{head}."
    if range_mode:
        tail = " Market is ranging."
    elif trend == "none":
        tail = " No clear trend."
    else:
        tail = f" Trend is {trend}." + (" Countertrend trade." if countertrend else "")
    return sentence + tail
