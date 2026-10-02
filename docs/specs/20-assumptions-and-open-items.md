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
| A20 | Which pivots the 3/8 planner uses | "Nearest pivot", "furthest pivot" | Daily pivots only for stop and target; weekly and monthly still count as indicator touches | Decided 2026-10-01 | 06 |
| A21 | Daily target minimum (60 pips) | Daily target 60 to 75 pips | Setting `reject_below_min` on the Target rule; off by default, so the minimum is shown only | Owners decide in Settings | 06 |
| A22 | "Price trades within N pips" | Not defined | Any part of the bar (high to low) within N pips of the level; the signal shows the distance from the close | Decided 2026-10-01 | 06 |
| A23 | Several trigger levels on one bar | Not stated | At most one long and one short candidate per bar. The trigger is the nearest fired pivot; a Fibonacci level triggers only when no pivot fired (A4) | Decided 2026-10-01 | 06 |
| A24 | Worked example levels | Daily S1 1.08360, S2 1.08200, R1 1.09100 and PDH 1.09050 | These pivots imply a prior-day high of 1.09520, so they cannot come from the same day as PDH 1.09050. The fixture supplies the levels directly. | Noted | 06, 17 |
| A25 | 3/8 cooldown | Spec 10 only | Rule `three_eight.cooldown`, 4 bars, provisional | Provisional | 10 |
| A26 | Econ window and countertrend | Countertrend allowed only off a large bar after a report | Inside the econ window the econ rule decides a countertrend candidate (large bar or not); the countertrend move rule applies outside it. A large bar plus a reversing candle lifts the stop maximum only when no stop within the limits exists | Provisional | 06 |
| A27 | Countertrend reward to risk | Target capped at 25 pips; stop at least 20 | Consequence, not a choice: a countertrend trade can never exceed 1.25 reward to risk, and passes only with a 20-pip stop. Owners may want to review the caps after the backtest | Noted | 06, 12 |
| A28 | Shaved head or bottom | "Shaved head or bottom" | A bullish bar with almost no upper shadow counts long; a bearish bar with almost no lower shadow counts short | Provisional | 06 |
| A29 | Provisional flag on a signal | "Provisional indicators always show the provisional badge" | `has_provisional` is set when a fired indicator is provisional (matches the spec 10 example, where entry and target rules are provisional but the flag is false) | Provisional | 10 |

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
| T3 | Chart library attribution requirement | Confirm in the TradingView Lightweight Charts license before release. Until then the signal chart keeps the library's TradingView logo link (its default) |
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
| 2026-10-01 | Add a `strategy_configs` table: one row per strategy with an on/off switch and the pairs it scans (resolves CLAUDE.md and spec 09 disagreement) |
| 2026-10-01 | First admin email added by `db/seed-admin.sh`, not the SQL seed |
| 2026-10-01 | Web image built from the repository root so it carries dbmate and the migrations for the pre-deploy step |
| 2026-10-02 | Dashboard status line shows the current New York time instead of a forex session name (spec 13 "current session"; closes open item T8) |
| 2026-10-02 | Provisional badge text uses a darker violet (`--prov-ink`, #5B44B8) in the light theme so it meets 4.5:1 on the selected-row fill; the dashed border keeps the design's `--prov` |
| 2026-10-03 | Signal and update notifications older than 2 hours are not sent (after a worker outage); the signals still appear in the portal |
| 2026-10-03 | Health alerts always reach admins by email, even if they turned email off, plus Telegram when linked; owners never get health alerts |
| 2026-10-02 | The scanner holds a Postgres advisory lock while its scheduler runs, so a redeploy that briefly starts a second copy waits instead of running jobs twice |
| 2026-10-02 | The web pre-deploy step registers the Telegram webhook from `APP_URL` and `TELEGRAM_WEBHOOK_SECRET` on every deploy; a Telegram error is logged and never fails the deploy |
| 2026-10-02 | Railway health check for web is `/sign-in`, not `/api/health`, so stale market data or a stopped scanner never blocks a web deploy; the uptime monitor keeps `/api/health` |
| 2026-10-02 | The web service raises the "scanner heartbeat is late" alert itself, checking every minute, because a stopped scanner cannot. It shares the scanner's `health_alerts` row (hourly repeat), and the scanner sends "Resolved" when it is back. `HEALTH_WATCHDOG=off` turns the check off (tests only) |
