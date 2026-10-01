# Strategy: Fibonacci Pivot Point

Source: handwritten Fibonacci Pivot Point notes. Instruments: every enabled forex pair. Levels are set once per New York trading day; triggers are checked on each completed 15-minute bar.

## The method, as written

- Take the day's high and the day's low and find the difference (the notes literally say subtract the high from the low; the worked example subtracts the low from the high, which is the only reading that gives a positive range).
- Find the Fibonacci number closest to that range.
- Starting from that number, take it and the next three Fibonacci numbers. The notes show the case where the closest number is 55, giving 55, 89, 144, 233.
- Build levels around the close: Break, Confirmation, Take Profit, Reset above and below.

Worked example from the notes: high 10.59, low 9.93, range 0.66, closest to 55, so the offsets are 0.55, 0.89, 1.44, 2.33.

## Codified rule

### Units

The notes work in hundredths of the price (cents on a stock priced in dollars). For forex the natural unit is the pip, which preserves the method's scale: a 66-pip day maps to 55, exactly like the 66-cent day in the notes.

| Key | Status | Definition | Defaults |
|---|---|---|---|
| `fib_pivot.unit` | Provisional | Unit used to convert the range to a Fibonacci number. Forex: pips. Stocks (if enabled later): 0.01 of price. | `forex_unit=pip` |

### Level calculation

| Key | Status | Definition | Defaults |
|---|---|---|---|
| `fib_pivot.levels` | Approved (with the unit interpretation above) | 1. Range in units = (prior day high - prior day low) / unit. 2. Find the closest number in the Fibonacci sequence 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987 (ties go to the larger number). 3. Offsets F0, F1, F2, F3 are that number and the next three. 4. Pivot = prior day close. 5. Levels: Break = Pivot +/- F0, Confirmation = Pivot +/- F1, Take Profit = Pivot +/- F2, Reset = Pivot +/- F3 (offsets converted back to price with the unit). | `min_fib=13`, `max_fib=987` |

The day is the New York trading day ending at 17:00.

Example in forex terms: EUR/USD prior day high 1.08950, low 1.08290, close 1.08700. Range 66 pips, closest Fibonacci number 55. Levels:

| Level | Long side | Short side |
|---|---|---|
| Reset | 1.11030 (+233) | 1.06370 (-233) |
| Take Profit | 1.10140 (+144) | 1.07260 (-144) |
| Confirmation | 1.09590 (+89) | 1.07810 (-89) |
| Break | 1.09250 (+55) | 1.08150 (-55) |
| Pivot | 1.08700 | 1.08700 |

### Trade plan

The notes give the levels but no entry, stop, or exit instructions. The launch plan:

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `fib_pivot.entry` | Provisional | A long candidate forms when a completed 15-minute bar closes above the upper Break. A short candidate forms on a close below the lower Break. Entry is that bar's close. | `trigger=close_beyond` (`close_beyond` or `touch`) |
| `fib_pivot.confirmation` | Provisional | When price reaches the Confirmation level in the trade direction, the signal is marked confirmed and an update notification is sent. | `notify_on_confirm=true` |
| `fib_pivot.stop` | Provisional | Stop at the Pivot (the prior close). | `stop_at=pivot` (`pivot` or `opposite_break`) |
| `fib_pivot.target` | Provisional | Target at Take Profit. | `target_at=take_profit` (`confirmation`, `take_profit`, `reset`) |
| `fib_pivot.reset` | Provisional | If price reaches Reset, the signal is marked extended and an update notification is sent. | `notify_on_reset=true` |
| `fib_pivot.one_per_side` | Provisional | At most one long and one short signal per pair per day. | `max_per_side_per_day=1` |
| `fib_pivot.window` | Provisional | Triggers are checked during the 3/8 trading window by default so the two systems share a schedule. | `window=primary` |
| `fib_pivot.expiry` | Provisional | Open signals expire at the 17:00 New York roll. | `expire_at_day_roll=true` |

### Why stop at the Pivot by default

An earlier draft proposed stopping at the opposite Break. With offsets of 55 and 144, that puts 110 units of risk against 89 units of reward (entry at +55, target at +144), a ratio below 1. Stopping at the Pivot risks 55 for the same 89, a ratio of about 1.6. Both options remain available as a setting, and the backtest compares them.

### Signal content

Each Fibonacci Pivot signal carries: the range in units, the chosen Fibonacci number, the full ladder, which level triggered, and the stop and target choices in effect. Indicators: there is no 3/8 count; the signal shows "Break" as the trigger and later adds "Confirmation reached" and "Reset reached" as events.

## Relationship to the 3/8 Formula

The two systems run independently. When a 3/8 signal and a Fibonacci Pivot signal agree in direction on the same pair within `confluence_bars` (default 4), the dashboard shows a confluence marker on both. Confluence does not change either signal's rules.
