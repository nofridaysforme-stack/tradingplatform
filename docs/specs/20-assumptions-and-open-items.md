# Assumptions and Open Items

Every interpretation the build relies on, in one place. Owners review this list after the backtest and during the paper run. Each provisional item is a setting in Settings > Rules, so changing it needs no code.

## Interpretations of the documents

| # | Topic | Document says | Build assumes | Status | Where |
|---|---|---|---|---|---|
| A1 | Timeframe for the 3/8 Formula | Mentions 15-minute candles and "4 candles" | 15-minute bars | Provisional | 06 |
| A2 | Time zone for trading hours | 12:00AM to 10:30AM (alt 5:00AM to 2:00PM), no zone | New York time | Provisional | 06 |
| A3 | Trend definition | Higher highs and higher lows | ZigZag swings with a 20-pip threshold on M15 | Approved concept, provisional threshold | 06 |
| A4 | Trigger location | Trades triggered off pivots; only exception FIBS | Candidate exists only at a pivot zone or a Fib level | Approved | 06 |
| A5 | "Furthest pivot" target | Target is always furthest pivot unless resistance | Furthest pivot within 75 pips, capped at PDH or PDL when it lies between | Provisional | 06 |
| A6 | Trendlines, channels, flags, pennants, triangles | Visual definitions | Algorithmic detection with stated thresholds | Provisional | 06 |
| A7 | Thrust candle and hook reversal | Count "sometimes" | Shown as supporting evidence, not counted | Provisional | 06 |
| A8 | Econ "large 15 min candle" | No size given | 25 pips | Provisional | 06 |
| A9 | Range mode flexibility | "Show more flexibility" | Same minimum of 3 by default; admins may lower to 2 | Provisional | 06 |
| A10 | Signal expiry | Not stated | End of trading window or 16 bars | Provisional | 06 |
| A11 | Fib Pivot units | Example in dollars and cents | Pips for forex | Provisional | 07 |
| A12 | Fib Pivot base number | Example uses 55 | Closest Fibonacci number to the range, then the next three | Approved | 07 |
| A13 | Fib Pivot entry, stop, target | Not stated | Close beyond Break, stop at Pivot, target at Take Profit | Provisional | 07 |
| A14 | Fib Pivot stop change | Earlier conversation proposed the opposite Break | Pivot by default because the opposite Break gives a ratio below 1; both are settings | Provisional | 07 |
| A15 | Stock liquidity filter | None | Minimum price $1, minimum 20-day average volume 100,000 | Provisional | 08 |
| A16 | 52-week high and low | Newspaper figures | Highest high and lowest low over 252 sessions | Approved | 08 |
| A17 | Stock alert timing | Not stated | Evening digest of newly trend-confirmed stocks | Provisional | 08 |
| A18 | Daily target 60 to 75 pips | Stated | Kept as default, flagged because current EUR/USD daily ranges average about 50 pips; backtest tests lower bands | Approved, under review | 06, 12 |
| A19 | Rule 2 and Rule 3 overlap | Listed as separate rules | Both kept; identical at defaults | Approved | 08 |

## Missing materials

| # | Item | Impact | Next step |
|---|---|---|---|
| M1 | 10 Line Chart instructions ("attached" in the documents) | Not built | Ask the owners for the pages |
| M2 | 12 Line Chart, Daily Tracking chart, Tracking Grid | Not built | Ask the owners for the pages |
| M3 | Author's intended pair list | Using the seven USD majors | Confirmed by the owners |

## Technical open items

| # | Item | Default until decided |
|---|---|---|
| T1 | Automated economic calendar source | Manual entry by admins |
| T2 | OANDA practice or live environment for data | Use the account the owners hold |
| T3 | Chart library attribution requirement | Confirm in the TradingView Lightweight Charts license before release |
| T4 | Railway Postgres backup retention on the chosen plan | Confirm during setup |
| T5 | Resend and uptime monitor free-tier limits | Confirm during setup |
| T6 | Broker list and typical spreads | Owners enter during Phase 5 |
| T7 | Domain name | Owners choose |

## Decisions log

| Date | Decision |
|---|---|
| 2026-10-01 | Personal use by the owners only |
| 2026-10-01 | All three systems in scope |
| 2026-10-01 | Seven USD majors at launch; owners can add pairs |
| 2026-10-01 | Multiple broker profiles; no trade execution |
| 2026-10-01 | Build with provisional definitions; approve later in Settings |
| 2026-10-01 | Host on Railway |
