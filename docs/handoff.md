# Handoff

The state of the project as of 2026-10-14. Read this with `CLAUDE.md` at the start of a new session. `CLAUDE.md` holds the standing rules; the specs in `docs/specs/` hold the design; this file holds what is live, what is waiting, and on whom.

Start a new session with: "Read docs/handoff.md and CLAUDE.md, then continue."

## Who and what

- The owner of this project (the portal builder) works with a small group of client business owners who will see, test, and pay for the portal before it gets a real domain.
- The clients' current focus is the **stock system**. Forex is paused at the client's request: hidden, not deleted.
- Staging on Railway is the only environment: services `web`, `scanner`, `postgres`, at the Railway-provided web domain. No custom domain yet, by choice.

## What is live (all merged into `main`)

| Area | State | Where |
|---|---|---|
| Stock momentum system | The client's funnel: 100 percent APR and within 10 percent of the 52-week high, then, on the Friday close (Thursday when Friday is a holiday), the 10-week filter: at least 5 of the 10 weekly rates (5 to 50 days back) at 455 percent APR. A pass is the qualifying date and keeps the stock on the watch list for 40 sessions, even through a drop below the 10 percent zone. Then a buy on 3 of 5 indicators inside 3 sessions (bullish candle in the pullback zone, MACD crossover, pivot line over its 3-day average, RSI crossing above 30, Stochastics crossing above 20). Exits: 5 percent stop, then a 5 percent trailing stop once up 10 percent, or a 3 of 5 sell vote. The 35 percent is a projection, not an exit. No Fibonacci. | Spec 08; `services/scanner/scanner/strategies/stock_momentum.py`; migrations `20261008000002` and `20261020000001` |
| Forex | Paused by `app_settings.forex_enabled = false`. Pages and jobs hide or skip themselves. Turning it back on is one setting. | Migration `20261008000001`; `apps/web/lib/app-settings.ts` |
| Sign-in | Email magic links cannot reach clients yet (Resend's test sender only delivers to the Resend account owner). Instead an admin opens Settings, Users, presses **Create sign-in link**, and texts the link. Links last 24 hours and work once; a continue page stops message previews from using them up. | PRs #25 and #26 |
| Stock storage | Only the stock universe (active common stocks on NYSE, Nasdaq, NYSE American) and held stocks are stored. The backfill refreshes the ticker list first and purges other rows. | PR #27; spec 04 |
| Telegram | Built and tested. Connecting the bot turns Telegram alerts on; disconnecting turns them off. Needs the bot and variables below before it works. | PR #28; spec 11 |
| Stock screen timing | Massive's free plan refuses the same-day file (403), so the 18:30 run defers and the 06:30 New York catch-up screens the previous session before the open. With a paid plan the evening run works and the catch-up finds nothing to do. The owner guide still says 6:30 pm. | Spec 16; `scanner/scheduler.py` |
| Owner guide | `docs/owner-guide.pdf`, second edition (2026-10-27): the stock system, sign-in links, Telegram. Forex appears only as paused. | |

## Waiting on the project owner (Railway and accounts)

1. **Database space.** The first stock backfill stopped at 110 of 300 sessions with "No space left on device". Upgrade Railway to Hobby and grow the Postgres volume (5 GB is plenty), then redeploy the scanner.
2. **Finish the data**, in the scanner service console. The console shell uses the system Python, so write `/app/.venv/bin/python` where these say `python`:
   - `python -m scanner.jobs.backfill stocks` (resumes; skips stored sessions)
   - `python -m scanner.jobs.stock_eod --date <last trading day>`
   - `python -m scanner.backtest.stocks --report out/stocks`
   After this the Health page shows a time for "Last stock screen". Until a screen runs, its Massive line says it is waiting for the first screen.
3. **Telegram.** Create a bot with BotFather. On `web` set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_WEBHOOK_SECRET` (48 random hex characters); on `scanner` set `TELEGRAM_BOT_TOKEN`. The web deploy log should show `telegram-webhook: registered`. Each person then taps Connect Telegram in Settings, Notifications and sends a test.
4. **Users list.** Check Settings, Users for a mistyped admin email (one entry was one letter off the owner's address).

## Waiting on the client

- Confirm the provisional assumptions **A31, A33 to A36** in `docs/specs/20-assumptions-and-open-items.md` (A30, A32, and A37 are approved). The most important:
  - A36: indicator settings. With the default RSI 14 and Stochastics 14, those two rarely vote during a pullback under 10 percent, so most buys come from the candle, MACD, and pivot. The client should say whether that is intended or give shorter lengths.
- Review the backtest report once it exists, so everyone knows how often the system finds trades.

## Later (not now, by the owner's decision)

- A real domain, a verified Resend sender (then email sign-in and email alerts reach clients), and a separate production Telegram bot. See `docs/production.md`.

## How work is done here

- One concern per pull request. Run the checks in `CLAUDE.md` before pushing; open a PR, wait for CI, and merge only when the owner asks.
- No trading features, broker credentials, or auto-execution (spec 18). Allowlist only; no public pages. Never commit keys and never ask for keys to be pasted into chat.
- UI copy and docs: sentence case, plain verbs, no em dashes.
- Never change a trading rule silently. If a rule question is not answered in spec 20, ask.
- Local test setup: Postgres 16 on port 5432 (`postgres:postgres`); apply migrations with `npx dbmate --migrations-dir migrations up` from `db/`; scanner tests need `TEST_DATABASE_URL` pointing at a freshly migrated database; e2e needs `DATABASE_URL`, `CHROMIUM_PATH=/opt/pw-browsers/chromium`, and a fresh `pnpm build`.
