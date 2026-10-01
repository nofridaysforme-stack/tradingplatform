# Trade Signal Portal: Spec Set

This folder is the complete specification for a private trade-alert portal that scans the forex and US stock markets using the owners' three trading systems and notifies them when a trade is suggested.

## How to use this set

1. Create the repository (see `03-architecture.md` for the layout).
2. Copy `01-CLAUDE.md` to the repository root and rename it `CLAUDE.md`. Claude Code reads it at the start of every session.
3. Copy every other file into `docs/specs/` in the repository.
4. Give `13-screens-and-design-brief.md` to Claude Design.
5. Follow `19-build-plan-and-prompts.md` phase by phase. Each phase ends with a sign-off gate. Do not start a phase until the previous gate is signed off.

## File index

| File | Purpose | Primary reader |
|---|---|---|
| 00-README.md | This index | Jana |
| 01-CLAUDE.md | Repository memory file: stack, conventions, guardrails | Claude Code |
| 02-product-requirements.md | Scope, users, features, non-goals, acceptance criteria | Everyone |
| 03-architecture.md | Components, repository layout, data flow, hosting | Claude Code |
| 04-data-sources.md | OANDA and Massive adapters, candles, time, pip sizes | Claude Code |
| 05-rules-engine.md | Config-driven rule framework, versions, statuses | Claude Code |
| 06-strategy-3-8-formula.md | 3/8 Formula codified rule by rule | Claude Code, owners |
| 07-strategy-fibonacci-pivot.md | Fibonacci Pivot Point method codified | Claude Code, owners |
| 08-strategy-stock-screener.md | Financial Wealth Building stock system codified | Claude Code, owners |
| 09-database-schema.md | Postgres schema as SQL | Claude Code |
| 10-signal-lifecycle.md | Signal object, states, dedupe, outcomes, broker adjustment | Claude Code |
| 11-notifications.md | Web push, email, Telegram, preferences, delivery | Claude Code |
| 12-backtesting.md | Backtest harness, cost model, metrics, report | Claude Code |
| 13-screens-and-design-brief.md | Screens, components, states, visual direction | Claude Design |
| 14-api-contracts.md | Web routes, server actions, worker health | Claude Code |
| 15-auth-and-security.md | Invite-only access, roles, secrets, audit | Claude Code |
| 16-deployment-and-operations.md | Railway services, env vars, schedules, monitoring, runbook | Claude Code, Jana |
| 17-testing-and-qa.md | Test strategy, fixtures, acceptance tests | Claude Code |
| 18-compliance-guardrails.md | Personal-use boundary, data licenses, contract notes | Jana, owners |
| 19-build-plan-and-prompts.md | Phases, gates, Claude Code kickoff prompts | Jana |
| 20-assumptions-and-open-items.md | Every assumption and provisional item in one place | Jana, owners |

## Source material

The trading rules come from the owners' documents, transcribed into eleven Markdown files:

- 3/8 Formula, pages 1 to 4
- Financial Wealth Building (Step 1, Step 2, Steps 3 to 5, Entry Points and Sales Targets, Financial Wealth Building 1)
- Newspaper stock table clip-out
- Fibonacci Pivot Point (handwritten)

Where a document is ambiguous, the spec states the interpretation, marks it provisional, and makes it a setting the owners can change.

## Decisions already made

| Decision | Choice |
|---|---|
| Who uses it | The owners only, for their own trading. No outside subscribers. |
| Systems in scope | All three: 3/8 Formula, Fibonacci Pivot, stock screener |
| Starting instruments | The seven USD majors: EUR/USD, GBP/USD, USD/JPY, USD/CHF, USD/CAD, AUD/USD, NZD/USD |
| Instruments later | Owners add, pause, and remove pairs in Settings |
| Brokers | Multiple broker profiles. Owners switch the active broker. The portal never places trades. |
| Rule definitions | Build with current definitions now. Judgment-call rules ship as provisional and are approved later through Settings. |
| Hosting | Railway for the portal, worker, and database |
