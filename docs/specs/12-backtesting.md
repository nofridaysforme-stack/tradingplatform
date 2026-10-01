# Backtesting

The backtester answers one question before the owners rely on any alert: would these exact rules, with realistic costs, have produced an edge on historical data?

## Principle

The backtester imports the same strategy modules and rule versions as the live worker. It replays completed bars in order, builds the same context, and records the same signal objects. Any difference between backtest and live behavior is a bug.

## Data

| Strategy | Source | Depth |
|---|---|---|
| 3/8 Formula, Fibonacci Pivot | OANDA candles API (M15 and D, mid prices), paged 5000 bars per request | 2016 to present (about 10 years) |
| Stock screener | Massive grouped daily bars already stored | 2 years (free plan limit) |

Downloaded history is cached as Parquet files in `services/scanner/.cache/history/` so repeat runs are fast. The cache is not committed.

## Engine

```
for bar in bars (chronological):
    update context incrementally (swings, levels at day roll)
    track open simulated signals against this bar
    evaluate strategy on this bar (completed bars only)
    record new signals
```

- Levels for day D use only data through the 17:00 New York close of day D-1.
- Swings are confirmed only after the ZigZag threshold is exceeded; the engine must never use a swing point before it would have been known live (no look-ahead).
- One simulated position per signal; signals are independent (the portal suggests, the owners decide).

## Cost model

| Cost | Default | Setting |
|---|---|---|
| Spread | The selected broker profile's typical spread per pair; if none, 1.0 pip on majors, 1.5 on USD/JPY and others | `--broker` or `--spread-pips` |
| Slippage | 0.5 pip on entry and on stop exits | `--slippage-pips` |
| Same-bar ambiguity | Count as stop hit | fixed |

## Validation design

- **In-sample / out-of-sample split.** Tune parameters only on the first 70 percent of the period. Report the final 30 percent separately and treat it as the real result.
- **Walk-forward (optional).** Rolling 2-year tune, 6-month test windows.
- **Minimum sample.** Do not draw conclusions from fewer than 100 trades for a configuration.
- **Parameter sweeps** are limited to a short list agreed with the owners (target band, stop band, Fib Pivot stop choice, minimum indicators, swing threshold). Large grids invite curve fitting.

## Metrics per strategy, pair, and configuration

| Metric | Definition |
|---|---|
| Trades | Count of closed simulated signals |
| Win rate | Target hits / trades |
| Average win, average loss | In pips |
| Expectancy | Average result per trade in pips, after costs |
| Profit factor | Gross wins / gross losses |
| Net pips | Sum of results |
| Max drawdown | Largest peak-to-trough decline in cumulative pips |
| Longest losing streak | Consecutive losses |
| Average reward-to-risk planned vs achieved | |
| Trades per week | |
| Rejection reasons | Counts of each gate failure, to show which rules filter most |
| Indicator frequency | How often each of the eight indicators fired in taken trades, and win rate when present |

Indicator frequency is the key input for approving provisional rules: it shows whether trendlines or flags improve results or only add noise.

## Report

`uv run python -m scanner.backtest.run --strategy three_eight --pairs EUR/USD,GBP/USD --start 2016-01-01 --end 2026-09-30 --broker "Broker A" --report out/`

Produces:
- `report.html`: summary table, equity curve per pair (cumulative pips), drawdown chart, monthly results grid, metrics tables, rejection reasons, indicator frequency, settings used
- `trades.csv`: every simulated trade with all fields from the signal payload
- `settings.json`: the exact version set and parameters

Reports are for the owners' internal use only.

## Questions the first backtest must answer

1. Does the 3/8 Formula show positive expectancy after costs out of sample on any pair?
2. Which daily target band fits current volatility (the document's 60 to 75 pips versus lower bands)?
3. Which Fibonacci Pivot stop (pivot or opposite break) performs better?
4. Do the provisional indicators (trendlines, flags) improve or dilute results?
5. Is the primary trading window better than the alternative window?

## Stock screener test

Run the screener on each stored session and measure, for each newly trend-confirmed stock, whether it reached a 30 percent gain within 20 sessions. Report the hit rate with an explicit note that the data excludes delisted companies and covers only two years.
