# Trade Signal Portal

A private trade-alert portal for the owners. A Python worker scans the forex and US stock markets using the owners' three trading systems (3/8 Formula, Fibonacci Pivot, stock screener) and notifies the owners when a trade is suggested. A Next.js portal shows signals, levels, history, and settings. The portal never places trades.

## Where things live

| Path | Contents |
|---|---|
| `CLAUDE.md` | Repository memory file for Claude Code: stack, conventions, guardrails |
| `docs/specs/` | Specification files 00 to 20. Start with `docs/specs/00-README.md`. |
| `apps/web/` | Next.js portal |
| `services/scanner/` | Python worker: data, rules, strategies, notifications, backtest |
| `db/migrations/` | Plain SQL migrations (dbmate), the single source of truth for the schema |

## How to build

Follow `docs/specs/19-build-plan-and-prompts.md` phase by phase. Each phase ends with a sign-off gate. Do not start a phase until the previous gate is signed off.
