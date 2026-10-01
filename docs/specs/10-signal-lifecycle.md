# Signal Lifecycle

## Signal payload

The worker builds this object, writes it to `signals`, `signal_indicators`, and `signal_events`, and passes it to the notification dispatcher.

```json
{
  "id": "6f1c...",
  "strategy": "three_eight",
  "instrument": "EUR/USD",
  "direction": "long",
  "state": "open",
  "bar_ts": "2026-10-05T08:00:00Z",
  "trading_day": "2026-10-05",
  "entry": "1.08420",
  "stop": "1.08190",
  "target": "1.09050",
  "alt_target": null,
  "risk_pips": 23.0,
  "reward_pips": 63.0,
  "reward_risk": 2.74,
  "indicator_count": 3,
  "minimum": 3,
  "has_provisional": false,
  "is_countertrend": false,
  "range_mode": false,
  "indicators": [
    {"key": "three_eight.pivot_touch", "name": "Pivots", "fired": true, "counted": true, "provisional": false, "level_ref": "daily.S1", "detail": {"level": "1.08360", "distance_pips": 6.0}},
    {"key": "three_eight.candlestick", "name": "Candlestick formation", "fired": true, "counted": true, "provisional": false, "detail": {"pattern": "Engulfing (bullish)"}},
    {"key": "three_eight.fibonacci", "name": "Fibonacci", "fired": true, "counted": true, "provisional": false, "level_ref": "fib.61.8", "detail": {"level": "1.08406", "leg": ["1.08100", "1.08900"]}},
    {"key": "three_eight.trendline_channel", "name": "Trendlines and channels", "fired": false, "counted": false, "provisional": true, "detail": {}}
  ],
  "gates": [
    {"key": "three_eight.trading_window", "passed": true, "detail": {"window": "primary", "ny_time": "04:15"}},
    {"key": "three_eight.reward_risk", "passed": true, "detail": {"ratio": 2.74, "min": 1.25}}
  ],
  "version_set": {"three_eight.pivot_touch": 1, "three_eight.candlestick": 1},
  "explanation": "Long at daily S1 with a bullish engulfing candle and the 61.8% retracement. Trend is up."
}
```

`explanation` is a template-built sentence (no AI generation), so it is deterministic and testable.

The payload always lists all eight 3/8 indicators, fired or not, so the portal can draw the full eight-segment indicator ring.

## States

```
             +-----------+
  created -> |   open    | --(fib pivot: confirmation reached)--> confirmed
             +-----------+                                            |
                  |                                                   |
     +------------+-------------+--------------+                      |
     v            v             v              v                      v
 target_hit    stop_hit      expired       invalidated     (same exits as open)
                                  
 ambiguous: target and stop both touched inside one bar
```

| State | Meaning |
|---|---|
| open | Plan is live |
| confirmed | Fibonacci Pivot only: price reached the Confirmation level |
| target_hit | A later bar's high (long) or low (short) reached the target first |
| stop_hit | A later bar's low (long) or high (short) reached the stop first |
| ambiguous | One bar touched both. Recorded as a loss in metrics (conservative). Shown with its own label. |
| expired | The expiry rule ended the signal before either level was reached; result is measured at the expiry bar's close |
| invalidated | An admin marked it invalid, or a data correction removed its triggering bar |

## Outcome tracking

On every new completed M15 bar for an instrument, before evaluating new candidates:

1. Load signals for that instrument in `open` or `confirmed`.
2. For each, check the bar against target and stop using reference prices.
3. Apply transitions, write `signal_events`, set `closed_at`, `exit_price`, `result_pips`.
4. Queue update notifications for owners with `include_updates=true`.

Result in pips: long `(exit - entry) / pip_size`; short `(entry - exit) / pip_size`. Outcomes are measured on reference mid prices; the history view can show results net of the active broker's spread.

## Dedupe

`dedupe_key` is built so the same setup cannot alert twice:

| Strategy | Key |
|---|---|
| three_eight | `three_eight:{instrument}:{direction}:{trigger level_ref}:{trading_day}` |
| fib_pivot | `fib_pivot:{instrument}:{direction}:{trading_day}` |
| stocks (digest) | `stocks:digest:{session_date}` |
| stocks (holding target) | `stocks:target:{holding_id}` |

A unique index enforces it. An insert conflict is not an error; the worker logs it at debug level.

Additional cooldown for the 3/8 Formula: no new signal on the same instrument and direction within `three_eight.cooldown.bars` (default 4) of the previous one, even at a different level. Status provisional.

## Broker adjustment

Signals are computed on mid prices. Each owner's view and notifications adjust for their active broker:

```
half = typical_spread_pips / 2 * pip_size
long:  entry_adj = entry + half    stop_adj = stop - half    target_adj = target - half
short: entry_adj = entry - half    stop_adj = stop + half    target_adj = target + half
```

Rationale: a long buys at the ask (above mid) and is closed by selling at the bid (below mid), so the levels at which a broker's chart triggers shift by half the spread. Reward-to-risk is recomputed with adjusted values and shown alongside the reference ratio.

If the owner has no active broker, reference prices are shown with the note "Reference prices. Choose a broker in Settings to see adjusted prices."

The "Open in broker" button fills `platform_url_template` with `{symbol}` (the broker's symbol override or the display symbol without the slash).

## Admin actions on a signal

- Mark invalid (with a reason). Writes an `invalidated` event and an audit entry. Metrics exclude invalidated signals.
- Add a note. Writes a `note` event.

Owners cannot edit signals.
