# Build Plan and Claude Code Prompts

Sequential phases with a sign-off gate after each. Design (Phase 3) runs in Claude Design in parallel with Phases 1 and 2. Durations assume focused part-time work and are estimates.

| Phase | Output | Duration | Gate (who signs off) |
|---|---|---|---|
| 0. Setup | Repository, CLAUDE.md, specs, CI, Railway staging, accounts | 1 to 2 days | Jana |
| 1. Data and schema | Migrations, seed, OANDA and Massive adapters, backfill, levels | 3 to 5 days | Jana: levels match hand calculations |
| 2. Rules and strategies | Rules engine, all indicators, three strategies, lifecycle, fixture tests | 1 to 2 weeks | Jana: all fixture tests pass |
| 3. Design | Screens and components in Claude Design | 2 to 4 days | Owners approve the design |
| 4. Backtest | Harness, reports for 3/8 and Fib Pivot on all seven pairs, stock hit-rate report | 3 to 5 days | Owners review results and choose launch parameters |
| 5. Portal | All screens wired to data, settings, rule management | 1 to 2 weeks | Jana: end-to-end tests pass |
| 6. Notifications | Web push, email, Telegram, preferences, health alerts | 3 to 4 days | Owners receive test alerts on every channel |
| 7. Staging run | 10 trading days of unattended operation | 2 weeks elapsed | Jana: staging acceptance list in spec 17 |
| 8. Production and paper run | Production deploy, 4 to 8 weeks of alerts with no money at risk | 4 to 8 weeks elapsed | Owners: ready to use live |

## Working method with Claude Code

- Start each phase in a fresh session. Paste the phase prompt below. Claude Code reads `CLAUDE.md` automatically and the specs on request.
- Ask for a plan first and approve it before code is written.
- Keep pull requests to one concern. Run tests before every merge.
- When Claude Code proposes changing a trading rule, decline and route it to `20-assumptions-and-open-items.md` for the owners.

## Phase prompts

### Phase 0: Setup
```
Read CLAUDE.md and docs/specs/00-README.md, 03-architecture.md, 16-deployment-and-operations.md.
Set up the monorepo exactly as specified: apps/web (Next.js App Router, TypeScript strict, Tailwind, shadcn/ui, pnpm), services/scanner (Python 3.12 with uv, ruff, mypy, pytest), db/migrations (dbmate).
Add Dockerfiles for web and scanner, a GitHub Actions workflow running lint, typecheck, and tests for both, and a .env.example listing every variable from spec 16.
Do not implement features yet. Show me the plan before writing files.
```

### Phase 1: Data and schema
```
Read docs/specs/04-data-sources.md, 09-database-schema.md, and the floor pivot and Fib Pivot level sections of 06 and 07.
1. Write the first dbmate migration implementing spec 09 exactly, plus the seed (instruments, rule definitions and version 1 from specs 06, 07, 08, revision row, heartbeat row, admin allowlist from SEED_ADMIN_EMAIL).
2. Implement the DataProvider protocols and the OANDA and Massive adapters with the shared Massive rate limiter, paging, complete-bar handling, and split refetch.
3. Implement backfill jobs and the levels modules (floor pivots, previous day, Fib Pivot ladder).
4. Write the adapter tests with recorded responses and the level fixture tests listed in spec 17.
Plan first, then implement in small commits.
```

### Phase 2: Rules engine and strategies
```
Read docs/specs/05-rules-engine.md, 06-strategy-3-8-formula.md, 07-strategy-fibonacci-pivot.md, 08-strategy-stock-screener.md, 10-signal-lifecycle.md, 17-testing-and-qa.md.
Implement the rules registry (loading versions, overrides, revision polling), every indicator as a pure function, the gates and planner for the 3/8 Formula, the Fib Pivot strategy, the stock screener, and the signal lifecycle (dedupe, cooldown, outcomes, expiry, broker adjustment helper).
Every parameter must come from the registry. Write every fixture in spec 17 first, then implement until they pass.
Wire the forex_bar_close, forex_day_roll, and stock_eod jobs to write signals and results, without notifications yet.
```

### Phase 4: Backtest
```
Read docs/specs/12-backtesting.md.
Implement the backtest harness that reuses the live strategy modules: history download and Parquet cache, chronological replay with no look-ahead, cost model, metrics, HTML report, trades.csv, settings.json.
Add the parity test from spec 17.
Then run: 3/8 Formula and Fib Pivot on all seven pairs, 2016-01-01 to the latest complete month, 70/30 split, default parameters, plus the sweeps listed in spec 12 section "Questions the first backtest must answer". Summarize the results for the owners in plain language with the tables.
```

### Phase 5: Portal
```
Read docs/specs/13-screens-and-design-brief.md, 14-api-contracts.md, 15-auth-and-security.md, and the approved design files from Claude Design in docs/design/.
Implement Auth.js magic link sign-in with the allowlist, the first-sign-in notice from spec 18, every screen in spec 13 using the approved design, the read endpoints and server actions in spec 14, and the rule management screens with schema validation, versioning, approval, overrides, and audit logging.
Add Playwright tests for the flows listed in spec 17 and axe checks.
```

### Phase 6: Notifications
```
Read docs/specs/11-notifications.md.
Implement the dispatcher in the scanner (filtering by preferences, quiet hours, retries, delivery log), web push with VAPID (manifest, service worker, subscribe and unsubscribe routes, iOS install guide), Resend email templates, Telegram linking and sending, the evening stock digest, holding alerts, and health alerts with resolve messages.
Add a "Send test notification" action. Test each channel end to end on staging.
```

### Phase 7 and 8: Staging run and production
```
Read docs/specs/16-deployment-and-operations.md and the staging acceptance section of 17.
Create a checklist issue for the 10-day staging run and the failure drill. After sign-off, configure the production Railway project, run migrations and seed, set OANDA_ENV per the owners' account, connect the domain, set up the uptime monitor, and walk through the runbook with me.
```

## Claude Design prompt (Phase 3)

```
Design a private trading desk web app for a few business owners. Use the attached brief (13-screens-and-design-brief.md) as the source of truth.
Start with the indicator ring component and the signal detail screen on mobile, then the dashboard on mobile, then history and rule settings on desktop.
Use real content from the brief: EUR/USD long, entry 1.08420, stop 1.08190, target 1.09050, reward to risk 2.74, indicators fired Pivots (daily S1), Candlestick (bullish engulfing), Fibonacci (61.8%).
Provide light and dark themes. Keep long and short distinguishable without color.
```
