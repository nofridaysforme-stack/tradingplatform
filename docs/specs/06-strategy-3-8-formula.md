# Strategy: 3/8 Formula

Source: 3/8 Formula pages 1 to 4. Timeframe: 15-minute bars (the document's econ rule refers to a "single large 15 min candle", and its countertrend rule counts movement "within 4 candles"). Instruments: every enabled forex pair.

Each rule below lists its key, status, and default parameters. **Approved** means the rule is stated directly in the document. **Provisional** means the document requires judgment and this is the launch interpretation.

## How a signal forms

1. A completed 15-minute bar arrives inside an allowed trading window.
2. Price is at a **trigger location**: a pivot zone, or a Fibonacci retracement level (the document allows only these two triggers).
3. The trigger location implies a direction: support below price means long, resistance above price means short.
4. At least **3 of the 8 indicators** fire in that direction.
5. All **gates** pass: trend alignment (or a valid countertrend exception), econ rules, stop feasibility, reward-to-risk.
6. The **planner** builds entry, stop, and target.

## Context the strategy builds each bar

| Item | Definition |
|---|---|
| Swings | Swing highs and lows from a ZigZag with a reversal threshold (`swing.threshold_pips`, default 20 on M15). Provisional parameter. |
| Last leg | The most recent completed swing-to-swing move |
| Trend state | `up` if the last two swing highs and last two swing lows are both higher; `down` if both lower; otherwise `none` |
| Floor pivots | Daily, weekly, monthly P, R1, R2, R3, S1, S2, S3 (formulas below) |
| PDH, PDL | Previous New York day high and low |
| Fib levels | Retracements of the last leg |
| Range state | Whether the market is transitioning or ranging (rule TR below) |
| Econ window | Whether a logged high-impact event for either currency occurred within the configured window |

### Floor pivot formulas (standard)

```
P  = (H + L + C) / 3
R1 = 2P - L          S1 = 2P - H
R2 = P + (H - L)     S2 = P - (H - L)
R3 = H + 2(P - L)    S3 = L - 2(H - P)
```

H, L, C are the previous day's, week's, or month's high, low, close on New York 17:00 alignment.

## The eight indicators

All eight have `kind=indicator` and `counts_toward_minimum=true`.

| # | Key | Name | Status | Definition | Defaults |
|---|---|---|---|---|---|
| 1 | `three_eight.candlestick` | Candlestick formation | Approved | One of the listed patterns completes on the signal bar or the bar before it, in the signal direction. Uses TA-Lib: CDLDOJI, CDLHAMMER, CDLINVERTEDHAMMER, CDLHARAMICROSS, CDLHANGINGMAN, CDLDARKCLOUDCOVER, CDLPIERCING, CDLSPINNINGTOP, CDLENGULFING. Shaved head or bottom: the bar's upper (or lower) shadow is at most `shaved_max_shadow_pct` of its range. Doji and spinning top are direction-neutral and count in the trigger's direction. | `lookback_bars=2`, `shaved_max_shadow_pct=5` |
| 2 | `three_eight.hl_failure` | New high/low failure | Approved | Price tests the high of the most recent up leg (for shorts) or the low of the most recent down leg (for longs) within `test_tolerance_pips` and the bar closes without exceeding it. | `test_tolerance_pips=5` |
| 3 | `three_eight.pivot_touch` | Pivots | Approved | Price trades within the tolerance of a pivot level: daily 10 pips, weekly 15, monthly 15. When daily and weekly (or monthly) levels sit within `double_pivot_pips` of each other, the detail is marked "double pivot". | `daily_tolerance_pips=10`, `weekly_tolerance_pips=15`, `monthly_tolerance_pips=15`, `double_pivot_pips=10` |
| 4 | `three_eight.flag_pennant_triangle` | Flags, pennants, triangles | Provisional | Pole: a move of at least `pole_min_pips` within `pole_max_bars`. Consolidation: `cons_min_bars` to `cons_max_bars` bars whose highs and lows fit converging or parallel regression lines. Fires on a close beyond the consolidation in the pattern's direction. Ascending flag and pennant are bullish; descending flag and reverse pennant are bearish. Projected target: the pole length from the breakout. | `pole_min_pips=30`, `pole_max_bars=6`, `cons_min_bars=4`, `cons_max_bars=20` |
| 5 | `three_eight.trendline_channel` | Trendlines and channels | Provisional | A trendline is a line through swing highs (or lows) with at least `min_touches` touches within `touch_tolerance_pips`. Fires when price touches a valid line in the signal direction (support for longs, resistance for shorts). A line becomes invalid on the first close beyond it by more than the tolerance. A channel exists when a parallel line through the opposite swings has slope difference within `parallel_tolerance_pct` and the swings form a clear V or inverted V. | `min_touches=3`, `touch_tolerance_pips=3`, `parallel_tolerance_pct=15`, `max_line_age_bars=480` |
| 6 | `three_eight.pdh` | Previous day's high | Approved | Price trades within `tolerance_pips` of PDH. Supports shorts at a rejection and longs on a confirmed break and retest. | `tolerance_pips=10` |
| 7 | `three_eight.pdl` | Previous day's low | Approved | Price trades within `tolerance_pips` of PDL. Mirror of PDH. | `tolerance_pips=10` |
| 8 | `three_eight.fibonacci` | Fibonacci | Approved | Price trades within `tolerance_pips` of a retracement of the last leg. Default ratios 0.382, 0.5, 0.618. The document also mentions 1/3, 1/2, 2/3; `ratio_set` switches between them. | `tolerance_pips=5`, `ratio_set=fib` (`fib` or `thirds`) |

### Supplementary indicators (shown, not counted by default)

| Key | Name | Status | Definition | Defaults |
|---|---|---|---|---|
| `three_eight.thrust_candle` | Thrust candle | Approved definition, provisional counting | A bar whose body is at least `min_body_pips` | `min_body_pips=15`, `counts_toward_minimum=false` |
| `three_eight.hook_reversal` | Hook reversal / blended hook | Provisional | After a leg of at least `min_leg_pips`, two consecutive bars form a reversal hook (second bar opens beyond and closes back inside the first bar's range) | `min_leg_pips=60`, `counts_toward_minimum=false` |

The document says these count "sometimes". They appear on the signal as supporting evidence. Admins can switch `counts_toward_minimum` on.

## Trigger location

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `three_eight.trigger` | Approved | A candidate exists only when indicator 3 (pivot) or indicator 8 (Fibonacci) fires on the bar. Direction is long when the level is at or below the bar's close, short when at or above. | none |

## Gates

| Key | Name | Status | Rule | Defaults |
|---|---|---|---|---|
| `three_eight.min_indicators` | Minimum indicators | Approved | Count of fired counting indicators in the candidate direction must be at least the minimum. The trigger indicator counts. | `minimum=3` |
| `three_eight.trading_window` | Trading hours | Approved | Bar close time (New York) inside the active window. Primary 00:00 to 10:30. Alternative 05:00 to 14:00. | `window=primary` (`primary`, `alternative`, `both`) |
| `three_eight.trend_alignment` | Trade with the trend | Approved | Direction must match trend state. If trend state is `none`, allowed only in range mode (rule TR). | none |
| `three_eight.countertrend` | Countertrend exception | Approved | A countertrend candidate is allowed only if: (a) the market has moved at least `min_move_pips` in the trend direction since the last opposite swing; (b) that move did not happen within `fast_move_bars` bars (a 50 to 60 pip move in 4 candles or less blocks countertrend trades); (c) after an 8-hour consolidation that resolves in the other direction, the move is treated as a new trend, not a countertrend. | `min_move_pips=50`, `fast_move_pips=50`, `fast_move_bars=4` |
| `three_eight.econ` | Econ reports | Approved | Within `window_minutes` after a logged high-impact event for either currency: a countertrend candidate is allowed only off a single 15-minute bar of at least `large_bar_pips`; a large move followed by a reversing candle formation is always allowed regardless of stop distance; Fibonacci levels may not be used as targets. | `window_minutes=60`, `large_bar_pips=25` (provisional value) |
| `three_eight.stop_feasible` | Stop placement possible | Approved | The planner must find a valid stop (see planner). If not, no trade. | none |
| `three_eight.reward_risk` | Target greater than risk | Approved | Target distance divided by stop distance must be at least `min_ratio`. The document's example is 25/20. | `min_ratio=1.25` |

## Planner

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `three_eight.entry` | Provisional | Entry is the close of the signal bar (reference mid price). Broker adjustment is applied later. | none |
| `three_eight.stop` | Approved | Trigger at a pivot: stop goes beyond the nearest pivot level on the far side of entry, and the distance must fall within `pivot_stop_min_pips` to `pivot_stop_max_pips`. Otherwise: stop goes `buffer_pips` beyond the previous swing high (shorts) or low (longs), using the smallest distance within 20 to 25 pips that clears it. If neither fits, the gate fails. | `pivot_stop_min_pips=20`, `pivot_stop_max_pips=25`, `buffer_pips=1`, `fallback_min_pips=20`, `fallback_max_pips=25` |
| `three_eight.target` | Provisional | Target is the furthest pivot level in the trade direction that (a) lies within `daily_target_max_pips` of entry and (b) is not beyond PDH (longs) or PDL (shorts) when that level lies between entry and the pivot; in that case the target is the PDH or PDL. Countertrend trades: target is the nearest Fibonacci level, then the nearest pivot, capped at `countertrend_target_max_pips`. Weekly pivot countertrend exception: target is the opposing weekly pivot. Pattern targets (indicator 4) are shown as an alternative target. | `daily_target_min_pips=60`, `daily_target_max_pips=75`, `countertrend_target_min_pips=20`, `countertrend_target_max_pips=25`, `reject_below_min=false` (owners decide whether a target closer than the minimum means no trade) |

### Daily target

The document sets a daily target of 60 to 75 pips. The portal shows each owner's progress toward it from closed signal outcomes. Rule `three_eight.daily_goal` with `suppress_after_goal=false` can stop new 3/8 alerts on a pair once the goal is reached that day.

Current EUR/USD daily ranges average near 50 pips, so the backtest must test lower target bands. All target parameters are per-instrument overridable.

## Range mode (transitioning market)

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `three_eight.range_detect` | Approved concept, provisional thresholds | The market is ranging when, over the last `lookback_bars` (8 hours = 32 bars), price has retested the same high or low at least `min_retests` times within `retest_tolerance_pips`, and the range width is at least `min_width_pips`. | `lookback_bars=32`, `min_retests=2`, `retest_tolerance_pips=5`, `min_width_pips=20` |
| `three_eight.range_mode` | Approved concept, provisional settings | In range mode: candidates must be inside the range; long near range low, short near range high; Fibonacci and countertrend candidates are allowed; the minimum indicator count uses `range_minimum`; targets cap at the opposite side of the range. | `range_minimum=3` |

The document says to "show more flexibility" in a ranging market. Admins can lower `range_minimum` to 2 after review.

## Signal expiry

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `three_eight.expiry` | Provisional | An open signal expires at the end of the trading window or after `max_bars` bars, whichever comes first. | `max_bars=16` |

## Worked example (for tests)

EUR/USD, trend `up`. The bar closes at 1.08420, 6 pips above daily S1 (1.08360). A bullish engulfing completes on this bar. The last leg runs 1.08100 to 1.08900; its 61.8 percent retracement is 1.08406. Indicators fired: pivot (daily S1), candlestick (engulfing), Fibonacci (61.8). Count = 3, minimum met. Trading window: 04:15 New York, primary window, pass. Stop: the nearest pivot beyond entry is S1 at 1.08360; placing the stop 1 pip beyond gives 1.08350, a 7 pip distance, below the 20 pip minimum, so the planner tries S2. With S2 at 1.08200, the stop is 1.08190, a 23 pip distance, valid. Target: the furthest pivot within 75 pips is R1 at 1.09100 (68 pips), and PDH 1.09050 lies between, so the target is 1.09050 (63 pips). Reward to risk 63 / 23 = 2.74, pass. Signal: long EUR/USD, entry 1.08420, stop 1.08190, target 1.09050.

This example becomes a fixture test.
