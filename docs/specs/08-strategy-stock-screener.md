# Strategy: Stock Momentum System (Financial Wealth Building)

Source: Financial Wealth Building pages (Step 1, Step 2, Steps 3 to 5), Financial Wealth Building 1 (three rules and five line chart), Entry Points and Sales Targets, the newspaper clip-out, and the owners' instructions of 2026-10-08 (momentum test, buy and sell vote, stops). Timeframe: daily bars, evaluated after each US session closes. Universe: US common stocks.

Revised 2026-10-08. The earlier version ended at "trend confirmed" with a 30 percent sales target. The owners now want a staged funnel: find strong stocks near their high, keep the ones moving fast enough, wait for a small pullback, buy when the indicators agree, and ride the trend until a stop or the indicators say sell. Every number below is a setting in Settings, Rules.

## The funnel

```
universe -> liquidity filter -> Stage 1 Qualify (Rules 1, 2, 3)
         -> Stage 2 Momentum (10-day rate at least 455%)
         -> Stage 3 Watch list (waits for a pullback inside the 10% zone)
         -> Stage 4 Buy (3 of 5 indicators within 3 sessions)
         -> Stage 5 Hold (35% projection shown, not an exit)
         -> Stage 6 Sell (fixed stop, trailing stop, or 3 of 5 sell indicators)
owner holdings -> the same stops and sell vote, on the owner's purchase price
```

A stock moves to the next stage only after passing the one before. Stages 1 to 3 run on every screened stock; stages 4 to 6 only on watched stocks and open buys.

## Universe and filters

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `stocks.universe` | Approved | Active common stocks on NYSE, Nasdaq, NYSE American (the documents say "comb through the entire NYSE and the Nasdaq"). | none |
| `stocks.liquidity` | Provisional | Exclude stocks below `min_price` or with 20-day average volume below `min_avg_volume`. The documents set no filter; this prevents untradeable penny stocks from flooding the list. Admins can set both to 0. | `min_price=1.00`, `min_avg_volume=100000` |
| `stocks.history_required` | Approved | A stock needs at least 252 sessions of history (the documents use 52-week figures) and 51 sessions for the 50-day close. | `min_sessions=252` |

52-week high and low use the highest daily high and lowest daily low over the last 252 sessions, matching newspaper convention.

## Stage 1: Qualify

| Key | Name | Status | Rule | Defaults |
|---|---|---|---|---|
| `stocks.rule1_near_high` | Close near the 52-week high | Approved | Last close >= 52-week high x `ratio`. The band between 90 percent of the high and the high is the **pullback zone**. | `ratio=0.90` |
| `stocks.rule2_double` | High at least twice the low | Approved | 52-week high >= 52-week low x `multiple`. | `multiple=2.0` |
| `stocks.rule3_apr` | Annual percentage rate | Approved | APR = (52-week high - 52-week low) / 52-week low. APR >= `min_apr`. | `min_apr=1.00` (100 percent) |

Rule 2 and Rule 3 are the same test written two ways at the default settings (a high at least twice the low always means a range of at least 100 percent of the low). Both are kept because they appear separately in the documents and can be tuned independently. The owners' "moving at a rate of 100% APR" is Rule 3, the 52-week figure from Step Two.

A stock that passes all three is **qualified**.

## Five line chart

For each qualified stock:

| Value | Definition |
|---|---|
| Today's close | Last session close C0 |
| N-day close | Close N sessions ago, for N = 5, 10, 20, 50 |
| ACC (actual percentage) for N | (C0 - CN) / CN |
| APR (annualized) for N | ACC_N / N x `trader_year` |

`trader_year` defaults to 260, as the documents specify.

Worked example from the documents: today 5.36, 5-day close 3.85. ACC_5 = 1.51 / 3.85 = 0.392207 (39 percent). APR_5 = 0.392207 / 5 x 260 = 20.3948 (2039 percent). This is a fixture test.

### Trend status (shown, not required)

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `stocks.trend_established` | Approved | The 20-day establishes a trend: ACC_20 > `min_acc`. | `min_acc=0` |
| `stocks.trend_confirmed` | Approved | The 50-day confirms the trend: ACC_50 > `min_acc` while the 20-day condition holds. | `min_acc=0` |
| `stocks.trend_consistent` | Provisional | The 5 and 10 day show consistent movement: ACC_5 and ACC_10 both > `min_acc`. Shown as a consistency flag. | none |

Status values: `qualified`, `trend_established`, `trend_confirmed`. They stay on the stock pages as context. The funnel does not require them unless `stocks.watch` sets `require_trend_confirmed` (open item A31).

## Stage 2: Momentum

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `stocks.momentum` | Approved concept, provisional settings | The stock's N-day APR from the five line chart is at least the rate that delivers `projection_pct` in `horizon_sessions`: threshold = `projection_pct` / 100 / `horizon_sessions` x `trader_year`. At the defaults that is 0.35 / 20 x 260 = **4.55 (455 percent)**, so the 10-day close must be about 17.5 percent below today's. | `period=10`, `projection_pct=35`, `horizon_sessions=20` |

The owners' words: "determine if the stock is capable of generating 455% with those 10 [days]. That will determine if the stock can generate 35% in a 20 day period." The 5 Line Bar example on the Steps 3 to 5 page shows the 10-day line at 1340 percent, the same kind of number. "10 week" in the note is read as the 10-day line (open item A30).

Changing `projection_pct` moves the threshold with it: 30 percent gives 390 percent.

## Stage 3: Watch list

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `stocks.watch` | Provisional | A qualified stock that passes Stage 2 joins the watch list that session. It stays on the list while it is still qualified (inside the pullback zone) for up to `watch_sessions` sessions after it last passed Stage 2. It leaves the list when it closes below the zone, when the time runs out, or when it is bought. | `watch_sessions=10`, `require_trend_confirmed=false` |

Why the stock stays on the list: a stock that gained 17.5 percent in 10 days rarely keeps that pace through a pullback. The momentum test is passed once; the buy comes during the pullback that follows. Requiring both on the same session would almost never buy (open item A32).

## Stage 4: Buy

Five indicators, each a separate rule. Each one **fires** on a session when its condition becomes true on that session's close. A cross means the value was on one side of the line at the previous close and on the other side at this close.

| Key | Name | Status | Buy fires when | Sell fires when | Defaults |
|---|---|---|---|---|---|
| `stocks.ind_candle` | Price and candle | Approved concept, provisional patterns | A bullish candle pattern completes on the session while the close is inside the pullback zone ("bullish candles on support") | A bearish candle pattern completes on the session | `bullish=[hammer, inverted_hammer, engulfing, piercing, morning_star, harami, dragonfly_doji]`, `bearish=[engulfing, dark_cloud_cover, hanging_man, shooting_star, evening_star, harami]` |
| `stocks.ind_macd` | MACD crossover | Approved | The MACD line crosses above its signal line | The MACD line crosses below its signal line | `fast=12`, `slow=26`, `signal=9` |
| `stocks.ind_pivot` | Pivot point crossover | Approved | The daily pivot line hooks above its 3-day average | The pivot line hooks below its 3-day average | `average_sessions=3` |
| `stocks.ind_rsi` | RSI | Approved buy level, provisional sell level | RSI crosses above `buy_level` | RSI crosses below `sell_level` | `period=14`, `buy_level=30`, `sell_level=70` |
| `stocks.ind_stoch` | Stochastics | Approved buy level, provisional sell level | Slow %K crosses above `buy_level` | Slow %K crosses below `sell_level` | `k_period=14`, `k_slowing=3`, `d_period=3`, `buy_level=20`, `sell_level=80` |

**Pivot line.** Each session's pivot point is (high + low + close) / 3. Day by day it forms a line; its average is the mean of the last `average_sessions` pivots. "Hooks above" is the pivot line crossing above that average.

**Candle patterns** use TA-Lib on daily bars (CDLHAMMER, CDLINVERTEDHAMMER, CDLENGULFING, CDLPIERCING, CDLMORNINGSTAR, CDLHARAMI, CDLDRAGONFLYDOJI for bullish; CDLENGULFING, CDLDARKCLOUDCOVER, CDLHANGINGMAN, CDLSHOOTINGSTAR, CDLEVENINGSTAR, CDLHARAMI for bearish). Engulfing and harami count by their sign. Without the Fibonacci, "support" is the pullback zone itself (open item A33).

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `stocks.buy_vote` | Approved | A watched stock gets a **buy** when at least `min_votes` different buy indicators fired within the last `window_sessions` sessions, counting today, and today's close is inside the pullback zone. | `min_votes=3`, `window_sessions=3` |

Each indicator counts once in the window however often it fired. At most one open buy per stock; a stock that is bought leaves the watch list until the buy closes.

**Entry** is the close of the buy session. Buys are evaluated after the close, so an owner acting on one buys at or after the next open; the portal shows the close it used.

## Stage 5: Hold

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `stocks.projection` | Approved | The buy shows a projected price of entry x (1 + `projection_pct` / 100) within `horizon_sessions`, with the daily and weekly targets from Entry Points and Sales Targets (total earnings / horizon, daily x 5). It is a guide, not an exit: the trade rides until Stage 6. | uses `stocks.momentum` `projection_pct` and `horizon_sessions` |
| `stocks.alert_projection` | Provisional | Send an information alert when the close first reaches the projected price. | on |
| `stocks.alert_horizon` | Provisional | Send an information alert when `horizon_sessions` pass without reaching it. | off |

## Stage 6: Sell

All exits use daily closes, never intraday prices (open item A34). Each session after the buy, in this order:

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `stocks.stop_loss` | Approved | Until the trade has gained `trail_after_pct`: a close at or below entry x (1 - `stop_pct` / 100) is a **stop** exit. | `stop_pct=5` |
| `stocks.trailing_stop` | Approved | Once the highest close since entry reaches entry x (1 + `trail_after_pct` / 100), the fixed stop is replaced by a trailing stop at the highest close x (1 - `trail_pct` / 100), rising as the price rises. A close at or below it is a **trailing stop** exit. The trailing stop never falls. | `trail_after_pct=10`, `trail_pct=5` |
| `stocks.sell_vote` | Approved concept, provisional mirror | A **sell signal** exit when at least `min_votes` different sell indicators fired within the last `window_sessions` sessions. | `min_votes=3`, `window_sessions=3` |

The stop is checked against the levels set by the previous session's close, then the highest close is updated. When a stop and a sell vote happen on the same session, the stop is the reason recorded.

Worked example: buy at 20.00. Fixed stop 19.00. The stock closes at 22.00 (+10 percent): the trailing stop starts at 20.90. It climbs to 26.00: the stop is 24.70. A close of 24.70 or lower exits at that close, +23.5 percent. Once the trailing stop is active the worst exit is about 4.5 percent above entry, because the highest close is at least 10 percent up.

The portal only alerts. Owners place and move any actual order or stop with their broker (CLAUDE.md rule 7).

## Holdings

Owners record purchases by hand: ticker, purchase price, purchase date, projection percent (default 35), horizon (default 20 sessions). A holding can be linked to the buy it came from. The same Stage 5 and Stage 6 rules run on each open holding from its own purchase price and date, using closes after the purchase date, and alert only the holding's owner.

| Value | Formula (from Entry Points and Sales Targets) |
|---|---|
| Projected price | Purchase price x (1 + projection). Example: 23.13 x 1.35 = 31.23. |
| Total earnings | Projected price - purchase price. Example: 31.23 - 23.13 = 8.10. |
| Daily target | Total earnings / horizon (20). Example: 8.10 / 20 = 0.405. |
| Weekly target | Daily target x 5. Example: 2.024. |
| Progress | (Last close - purchase price) / total earnings, and sessions elapsed of the horizon |
| Stop now | The fixed or trailing stop that applies after the last close |

The document's own example uses 30 percent (23.13 x 1.30 = 30.06); 35 percent is the owners' new default. The portal computes unrounded values and displays two decimals for prices and three for daily and weekly targets.

## Alerts

All evening, after the stock screen (spec 11 channels and preferences, strategy `stocks`).

| Alert | When | Who |
|---|---|---|
| Watch list | One digest listing stocks that joined the watch list today, best 10-day APR first, at most `max_in_digest` | Everyone with stock alerts on |
| Buy | One alert per buy: ticker, entry, stop, projection, and the indicators that voted | Everyone with stock alerts on |
| Sell | One alert per closed buy: reason (stop, trailing stop, sell signal), exit close, result in percent | Everyone with stock alerts on |
| Trailing stop started, projection reached | Information updates on an open buy (with "Updates" on) | Everyone with stock alerts and updates on |
| Holding stop, trailing stop, sell signal, projection reached | Same rules on the owner's holding | The holding's owner |

`stocks.alert_digest`: `max_in_digest=25`.

## What each record keeps (CLAUDE.md rule 3)

Each buy stores: ticker, buy session, entry, the stop and projection at the time, every indicator's result for the window (fired or not, on which session, and its values), the rule version set, and whether any rule that voted is provisional. Each exit stores its session, close, reason, and result. The screen result for each stock and session stores its stage (qualified, momentum, watching) and the day's indicator values, so the stock page can show why a stock is or is not moving through the funnel.

## Not yet in scope

The documents mention a 10 Line Chart (with "attached" instructions), a 12 Line Chart, a Daily Tracking chart, and a Tracking Grid. Those pages were not provided (spec 20, M1 and M2).

## Backtest

`python -m scanner.backtest.stocks` replays the funnel over the stored sessions with the same code: watch list entries, buys, exits by reason, win rate, average and median result in percent, average sessions held, and how often each of the five indicators voted in the buys. It runs before any change to these rules is switched on.

The stock backtest can only use the history on the data plan (two years on the free plan), and that history excludes companies that later delisted. Results overstate performance. The report says so.
