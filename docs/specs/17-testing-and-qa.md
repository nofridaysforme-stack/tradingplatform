# Testing and QA

## Layers

| Layer | Tool | Scope |
|---|---|---|
| Indicator unit tests | pytest | Every indicator function with hand-built candle fixtures: fires, does not fire, edge at tolerance, both directions |
| Gate and planner tests | pytest | Each gate pass and fail; stop and target selection including fallback paths |
| Strategy fixture tests | pytest | Full strategy runs on recorded bar sequences with expected signals (golden files) |
| Level tests | pytest | Floor pivots, PDH/PDL, Fib Pivot ladder against hand-calculated values |
| Lifecycle tests | pytest | Outcomes, ambiguous bars, expiry, dedupe, cooldown |
| Data adapter tests | pytest with recorded HTTP responses (respx) | OANDA candles paging and `complete` handling; Massive grouped bars, pagination, splits, rate limiter |
| Backtest parity test | pytest | Replaying a fixture day in the backtester yields the same signals as the live job path |
| Web unit tests | Vitest | Pip formatting, broker adjustment display, zod validators |
| Web end-to-end | Playwright | Sign-in (magic link captured in test mode), dashboard, signal detail, rule edit and approve, notification preferences |
| Accessibility | axe in Playwright | Key screens in both themes |

## Required fixtures (from the specs)

| Fixture | Expected result | Spec |
|---|---|---|
| `eurusd_worked_example.json` | Long, entry 1.08420, stop 1.08190, target 1.09050, R 2.74, indicators pivot, candlestick, Fibonacci | 06 |
| `floor_pivots_basic.json` | P, R1 to R3, S1 to S3 match the formulas to 5 decimals | 06 |
| `fib_pivot_notes_example.json` | High 10.59, low 9.93, close given: range 66 units, Fibonacci number 55, offsets 55, 89, 144, 233 | 07 |
| `fib_pivot_eurusd.json` | Ladder from 1.08700 with 55: Break 1.09250 and 1.08150, Confirmation 1.09590 and 1.07810, Take Profit 1.10140 and 1.07260, Reset 1.11030 and 1.06370 | 07 |
| `stock_five_line_example.json` | Today 5.36, 5-day 3.85: ACC_5 0.392207, APR_5 20.394805 | 08 |
| `stock_rules_calamp.json` | High 9.72, low 3.42, close 9.10: Rule 1 pass (9.10 >= 8.748), Rule 2 pass, APR 1.842 | 08 |
| `sales_target_example.json` | 23.13 at 30 percent: target 30.069, earnings 6.939, daily 0.34695, weekly 1.73475 | 08 |
| `countertrend_fast_move.json` | 55-pip move in 3 bars, then a countertrend candidate: rejected by the countertrend gate | 06 |
| `econ_window.json` | Countertrend candidate 20 minutes after a logged high-impact USD event, off a 28-pip bar: allowed; same with a 12-pip bar: rejected | 06 |
| `same_bar_ambiguous.json` | Bar touches stop and target: state `ambiguous`, counted as a loss | 10 |
| `usdjpy_pips.json` | Pip math with 0.01 pip size: 20 pips equals 0.20 | 04 |

## Coverage expectations

- 100 percent of indicator, gate, and planner functions have direct tests.
- Overall Python line coverage at least 85 percent for `scanner/indicators`, `scanner/strategies`, `scanner/levels`, `scanner/signals`.

## Staging acceptance (before production)

1. Ten consecutive trading days on staging: no missed `forex_bar_close` runs (check `job_runs`), no unhandled exceptions, heartbeat never stale.
2. Every owner receives a test notification on each enabled channel within 90 seconds.
3. Every rule appears in Settings with the correct status, parameters, and source reference.
4. A rule change on staging takes effect on the next bar and is visible in the audit log.
5. One forced failure drill: stop the scanner for 10 minutes and confirm the health alert and the "Resolved" message.

## Paper run (production, no money at risk)

- Duration 4 to 8 weeks, agreed with the owners.
- Weekly review: signal count per strategy and pair, outcomes, any signal an owner disagrees with (logged as a note with the reason).
- Exit criteria: owners are comfortable with the alert volume and quality, provisional rules have enough data to approve, change, or disable.
