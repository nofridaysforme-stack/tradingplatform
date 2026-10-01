# CLAUDE.md

Read this file at the start of every session. Specs live in `docs/specs/`. When a spec and this file disagree, stop and ask.

## What this project is

A private portal for a small group of business owners. A Python worker scans forex (15-minute bars) and US stocks (daily bars) using three rule-based trading systems, stores every suggested trade with the reasons it fired, tracks each suggestion's outcome, and notifies the owners. A Next.js portal shows signals, levels, history, and settings. The portal never places trades.

## Repository layout

```
/apps/web            Next.js (App Router, TypeScript) portal
/services/scanner    Python worker: data, rules, strategies, notifications, backtest
/db/migrations       Plain SQL migrations (dbmate). Single source of truth for the schema.
/docs/specs          Specification files 00 to 20
```

## Stack

| Area | Choice |
|---|---|
| Web | Next.js App Router, TypeScript strict, Tailwind CSS, shadcn/ui primitives, TanStack Query for polling |
| Web data access | Drizzle ORM in query-only mode against the SQL schema. Do not generate migrations with Drizzle. |
| Auth | Auth.js v5, email magic link via Resend, allowlist of approved emails |
| Charts | TradingView Lightweight Charts (open-source library). Confirm the attribution requirement in its license before release. |
| Worker | Python 3.12, pandas, numpy, TA-Lib (0.6.5 or later wheels), httpx, APScheduler, psycopg 3, pydantic v2 |
| Database | Postgres on Railway |
| Notifications | pywebpush (VAPID), Resend Python SDK, Telegram Bot API over httpx |
| Hosting | Railway: services `web`, `scanner`, `postgres` |

## Commands

```
# database
dbmate up                         # apply migrations
dbmate new <name>                 # create a migration

# web
cd apps/web && pnpm dev
cd apps/web && pnpm test
cd apps/web && pnpm lint && pnpm typecheck

# worker
cd services/scanner && uv sync
cd services/scanner && uv run pytest
cd services/scanner && uv run python -m scanner.main          # run the worker
cd services/scanner && uv run python -m scanner.backtest.run --help
```

## Non-negotiable rules

1. **One rules engine.** The live scanner and the backtester import the same strategy code from `services/scanner/scanner/strategies`. Never duplicate rule logic anywhere, including the web app. The web app reads results; it does not compute signals.
2. **Rules come from configuration.** Every threshold, pip distance, ratio, and toggle is a parameter in `rule_definitions` / `strategy_configs` (see `05-rules-engine.md`). No magic numbers inside strategy functions.
3. **Every signal explains itself.** A signal row is never written without its fired indicators, the rule version set that produced it, and the provisional flags.
4. **Only completed bars.** Strategies evaluate completed candles only. Never act on a forming candle.
5. **Time is explicit.** Store UTC. Convert to `America/New_York` only for session logic and display. The forex trading day rolls at 17:00 New York time.
6. **Pips come from the instrument.** Always convert with the instrument's `pip_size`. Never assume 0.0001.
7. **No trading.** Do not add order placement, broker credentials, or auto-execution. If asked, stop and point to `18-compliance-guardrails.md`.
8. **No outside users.** Access is allowlist only. Do not build public sign-up, sharing links, or public pages that show signals or performance.
9. **Secrets stay in environment variables.** Never commit keys. Never send the OANDA or Massive key to the browser.

## Code conventions

- Python: type hints everywhere, pydantic models for configs and signal payloads, `ruff` and `mypy --strict` clean, pure functions for indicators so they are unit-testable with fixture candles.
- TypeScript: strict mode, no `any`, server components by default, server actions for mutations, zod for input validation.
- Tests accompany every indicator, gate, and strategy. Fixture candle files live in `services/scanner/tests/fixtures/`.
- Small commits with clear messages. One concern per pull request.

## UI copy rules

- Sentence case. Plain verbs. Buttons say exactly what happens ("Save changes", "Add pair").
- No em dashes anywhere in UI copy or docs.
- Long and short are shown with color plus an icon and the word, never color alone.
- Provisional indicators always show the provisional badge.

## When unsure

Check `20-assumptions-and-open-items.md`. If the answer is not there, ask before inventing behavior. Never silently change a trading rule.
