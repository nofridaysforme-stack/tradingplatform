# Strategy: Stock Screener (Financial Wealth Building)

Source: Financial Wealth Building pages (Step 1, Step 2, Steps 3 to 5), Financial Wealth Building 1 (three rules and five line chart), Entry Points and Sales Targets, and the newspaper clip-out. Timeframe: daily bars. Universe: US common stocks.

## Pipeline

```
universe -> liquidity filter -> Rule 1 -> Rule 2 -> Rule 3 -> qualified list
qualified list -> five line chart -> trend status -> alerts
owner holdings -> sales targets -> progress and alerts
```

## Universe and filters

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `stocks.universe` | Approved | Active common stocks on NYSE, Nasdaq, NYSE American (the documents say "comb through the entire NYSE and the Nasdaq"). | none |
| `stocks.liquidity` | Provisional | Exclude stocks below `min_price` or with 20-day average volume below `min_avg_volume`. The documents set no filter; this prevents untradeable penny stocks from flooding the list. Admins can set both to 0. | `min_price=1.00`, `min_avg_volume=100000` |
| `stocks.history_required` | Approved | A stock needs at least 252 sessions of history (the documents use 52-week figures) and 51 sessions for the 50-day close. | `min_sessions=252` |

52-week high and low use the highest daily high and lowest daily low over the last 252 sessions, matching newspaper convention.

## Qualification rules

| Key | Name | Status | Rule | Defaults |
|---|---|---|---|---|
| `stocks.rule1_near_high` | Close near the 52-week high | Approved | Last close >= 52-week high x `ratio`. | `ratio=0.90` |
| `stocks.rule2_double` | High at least twice the low | Approved | 52-week high >= 52-week low x `multiple`. | `multiple=2.0` |
| `stocks.rule3_apr` | Annual percentage rate | Approved | APR = (52-week high - 52-week low) / 52-week low. APR >= `min_apr`. | `min_apr=1.00` (100 percent) |

Note for owners: with default settings, Rule 2 and Rule 3 are the same test written two ways (a high at least twice the low always means a range of at least 100 percent of the low). Both are kept because they appear separately in the documents and can be tuned independently.

A stock that passes all three is **qualified**.

## Five line chart (trend analysis)

For each qualified stock:

| Value | Definition |
|---|---|
| Today's close | Last session close C0 |
| N-day close | Close N sessions ago, for N = 5, 10, 20, 50 |
| ACC (actual percentage) for N | (C0 - CN) / CN |
| APR (annualized) for N | ACC_N / N x `trader_year` |

`trader_year` defaults to 260, as the documents specify.

Worked example from the documents: today 5.36, 5-day close 3.85. ACC_5 = 1.51 / 3.85 = 0.392207 (39 percent). APR_5 = 0.392207 / 5 x 260 = 20.3948 (2039 percent). This becomes a fixture test.

### Trend status

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `stocks.trend_established` | Approved | The 20-day establishes a trend: ACC_20 > `min_acc`. | `min_acc=0` |
| `stocks.trend_confirmed` | Approved | The 50-day confirms the trend: ACC_50 > `min_acc` while the 20-day condition holds. | `min_acc=0` |
| `stocks.trend_consistent` | Provisional | The 5 and 10 day show consistent movement: ACC_5 and ACC_10 both > `min_acc`. Shown as a consistency flag; not required for an alert by default. | `required_for_alert=false` |

Status values: `qualified`, `trend_established`, `trend_confirmed`.

### Ranking

The qualified list sorts by APR_20 descending by default, with columns for every five-line value so owners can re-sort.

## Alerts

| Key | Status | Rule | Defaults |
|---|---|---|---|
| `stocks.alert_new_confirmed` | Provisional | Alert when a stock reaches `trend_confirmed` today and was not `trend_confirmed` in the prior `cooldown_sessions`. One digest notification per evening lists all such stocks, not one alert each. | `cooldown_sessions=10`, `max_in_digest=25` |
| `stocks.alert_target_reached` | Approved | Alert when an owner's holding closes at or above its sales target. | none |
| `stocks.alert_time_elapsed` | Provisional | Alert when a holding reaches `horizon_sessions` without hitting its target. | `horizon_sessions=20` |

## Holdings and sales targets

Owners enter holdings manually (the portal has no broker connection): ticker, purchase price, purchase date, expected profit percent (default 30).

| Value | Formula (from Entry Points and Sales Targets) |
|---|---|
| Sales target | Purchase price x (1 + expected profit). Example: 23.13 x 1.30 = 30.07. |
| Total earnings | Sales target - purchase price. Example: 30.07 - 23.13 = 6.94. |
| Daily target | Total earnings / `horizon_sessions` (20). Example: 6.94 / 20 = 0.347. |
| Weekly target | Daily target x 5. Example: 1.735. |
| Progress | (Last close - purchase price) / total earnings, and sessions elapsed of 20 |

The document rounds the example to 30.06, 6.93, .34, and 1.73. The portal computes unrounded values and displays two decimals for prices and three for daily and weekly targets. Rounding differences from the document are expected.

## Not yet in scope

The documents mention a 10 Line Chart (with "attached" instructions), a 12 Line Chart, a Daily Tracking chart, and a Tracking Grid. Those pages were not provided. The data model leaves room for them; they are listed in `20-assumptions-and-open-items.md`.

## Historical caution

The stock backtest can only use the two years of history on the free data plan, and that history excludes companies that later delisted. Results from it overstate performance. The forex backtest has no such limitation.
