# Rules Engine

The engine turns the owners' written rules into configuration. Strategies are code; every number and switch they use is data.

## Concepts

| Concept | Meaning |
|---|---|
| Rule definition | One named rule or indicator, such as "Pivot touch" or "Stop placement". Has a plain-language description, parameters, status, and version. |
| Parameter | A named value with a type, default, allowed range, and unit (pips, bars, ratio, percent, minutes, boolean, enum). |
| Status | `approved` (taken directly from the documents) or `provisional` (an interpretation awaiting owner approval). |
| Version | Every change to a rule's parameters, description, or status creates a new immutable version. |
| Strategy config | The set of rule versions a strategy uses, plus per-instrument overrides. |
| Version set | The exact list of rule versions active when a signal fired. Stored on every signal. |

## Rule definition shape

```json
{
  "key": "three_eight.pivot_touch",
  "strategy": "three_eight",
  "kind": "indicator",
  "name": "Pivot touch",
  "description": "Price reaches a daily pivot level within 10 pips, or a weekly or monthly pivot within 15 pips.",
  "source": "3/8 Formula p1, Pivots",
  "status": "approved",
  "enabled": true,
  "counts_toward_minimum": true,
  "params": {
    "daily_tolerance_pips":   {"type": "pips", "default": 10, "min": 1, "max": 50},
    "weekly_tolerance_pips":  {"type": "pips", "default": 15, "min": 1, "max": 50},
    "monthly_tolerance_pips": {"type": "pips", "default": 15, "min": 1, "max": 50}
  }
}
```

`kind` is one of:
- `indicator`: contributes to a count (the 3/8 eight)
- `gate`: must pass for any signal (trading window, trend alignment, stop feasibility, reward-to-risk)
- `plan`: computes entry, stop, target
- `filter`: narrows a universe (stock liquidity)
- `lifecycle`: dedupe, expiry, outcome rules

## Per-instrument overrides

Any parameter can be overridden per instrument in `strategy_param_overrides`. Resolution order: instrument override, then the rule version's value, then the parameter default.

Pip-based defaults come from the documents, which were written for the major pairs. Owners tune them per pair after the backtest.

## Loading and caching

The worker loads all enabled rule versions and overrides at startup and re-reads them when `rule_config_revision` (a single counter row) changes. Every admin change increments it. The worker checks the counter before each bar evaluation.

## Evaluation pipeline (shared by all strategies)

```
build_context(instrument, bars, levels, econ_events)
    -> Context

for each indicator rule enabled:
    result = indicator.evaluate(context, params)   # IndicatorResult
collect fired indicators

for each gate rule enabled:
    gate.check(context, candidate, params)          # pass or fail with reason

plan = planner.build(context, candidate, params)    # entry, stop, target, R

if all gates pass and plan valid:
    signal = Signal(..., indicators, gates, plan, version_set, provisional_flags)
```

```python
class IndicatorResult(BaseModel):
    key: str
    fired: bool
    direction: Literal["long", "short", "either"] | None
    level_ref: str | None        # e.g. "daily.S1", "fib.61.8", "pdl"
    detail: dict                 # values used, for the explanation panel
    provisional: bool
```

Gate failures are logged at debug level with their reasons so the backtester can report why candidates were rejected.

## Approving a provisional rule

1. Admin opens Settings > Rules, selects the rule, reviews its history panel (signals that used it and their outcomes).
2. Admin edits parameters if needed and selects "Approve".
3. A new version is created with status `approved`. The change, the user, and the time are written to `audit_log`.
4. The worker picks up the new revision before the next bar.

## Disabling a rule

Disabling an indicator removes it from evaluation. For the 3/8 count, disabling reduces the pool of possible indicators; the minimum count stays as configured, so admins should review the minimum when disabling.

## Seed data

Migrations seed every rule from `06`, `07`, and `08` as version 1 with the documented defaults and statuses. The seed is the single place where document numbers enter the system.
