# Deployment and Operations

## Railway project

One Railway project per environment (`portal-staging`, `portal-production`), each with three services:

| Service | Build | Start | Notes |
|---|---|---|---|
| web | `apps/web/Dockerfile`, built from the repository root (Node LTS, pnpm build, standalone output, plus dbmate and `db/`) | `node server.js` | Public domain with HTTPS |
| scanner | `services/scanner` Dockerfile (Python 3.12 slim, `uv sync --frozen`) | `python -m scanner.main` | No public domain. One replica only (the scheduler must not run twice). |
| postgres | Railway Postgres | | Backups enabled |

Migrations run as a pre-deploy command on the web service: `/app/db/migrate.sh` (runs `dbmate --wait up`, then adds `SEED_ADMIN_EMAIL` to the allowlist). The scanner waits for the expected schema version at startup and exits with a clear error if it is behind.

Accounts (OANDA, Massive, Railway, Resend, Telegram bot) are opened in the client's business name. Jana is added as a collaborator during the build and support period.

## Environment variables

| Variable | web | scanner | Example or note |
|---|---|---|---|
| DATABASE_URL | yes | yes | Railway reference variable |
| APP_URL | yes | yes | `https://portal.example.com` |
| AUTH_SECRET | yes | | random 32 bytes |
| RESEND_API_KEY | yes | yes | |
| EMAIL_FROM | yes | yes | `Alerts <alerts@example.com>` (verified domain) |
| OANDA_API_TOKEN | | yes | |
| OANDA_ACCOUNT_ID | | yes | |
| OANDA_ENV | | yes | `practice` or `live` |
| MASSIVE_API_KEY | | yes | |
| VAPID_PUBLIC_KEY | yes | yes | |
| VAPID_PRIVATE_KEY | | yes | |
| VAPID_SUBJECT | | yes | `mailto:ops@example.com` |
| TELEGRAM_BOT_TOKEN | yes | yes | |
| TELEGRAM_BOT_USERNAME | yes | | |
| TELEGRAM_WEBHOOK_SECRET | yes | | |
| OPS_ALERT_EMAIL | | yes | Jana's or the admins' address |
| SEED_ADMIN_EMAIL | yes | | used once by the seed |
| LOG_LEVEL | yes | yes | `info` |

## Scanner schedule (APScheduler, times in UTC unless noted)

| Job | Schedule | What it does |
|---|---|---|
| heartbeat | every 60 s | Updates `worker_heartbeat` |
| forex_bar_close | minutes 0, 15, 30, 45 at second 5, while forex is open | Fetch, outcomes, strategies, notify (retries at +20 s and +40 s if the bar is not complete) |
| forex_day_roll | 17:01 America/New_York, Sunday to Friday | Daily levels, Fib Pivot ladder, weekly and monthly pivots when due, expire day-bound signals |
| stock_eod | 18:30 America/New_York on US trading days, retry every 15 min until 23:00 | Grouped bars, splits, screener, holdings, digest |
| ticker_refresh | Sunday 12:00 America/New_York | Refresh stock universe |
| retention | 03:00 daily | Delete expired rows |
| health_check | every 5 min | Staleness checks, health alerts |

Use APScheduler's timezone-aware cron triggers for the New York jobs so daylight saving changes are handled automatically. Set `max_instances=1` and `coalesce=True` on every job.

## Monitoring

- External uptime monitor (Better Stack or UptimeRobot free tier) polls `GET /api/health` every 5 minutes and alerts Jana.
- Scanner health alerts as defined in `11-notifications.md`.
- Structured JSON logs in both services; Railway log retention is enough for debugging. Optional: Sentry free tier for exceptions in both services.

## Deploy flow

1. Pull request with tests passing in GitHub Actions (lint, typecheck, pytest, web tests).
2. Merge to `main` deploys to staging automatically.
3. Promote to production by merging `main` into `production` (or a Railway manual promote) after staging checks.
4. Rule changes do not need a deploy; they are data.

## Runbook

| Symptom | Check | Fix |
|---|---|---|
| Health shows heartbeat stale | Scanner service status and logs in Railway | Restart the scanner service. If it crash-loops, roll back to the previous deploy. |
| One pair stale | OANDA status, instrument enabled, provider code correct | Wait for OANDA recovery; alerts for that pair resume automatically |
| All forex stale on a Sunday evening | Market opens Sunday 17:00 New York; first bar completes 17:15 | Expected, no action |
| Stock scan missing | `job_runs` for stock_eod; Massive status; rate limit errors | Rerun with `python -m scanner.jobs.stock_eod --date YYYY-MM-DD` |
| Owner not receiving push | Settings > Notifications shows blocked; iPhone not installed from Safari | Reinstall to Home Screen, turn notifications on, send a test |
| Telegram silent | `telegram_links.chat_id` present; bot token valid | Reconnect Telegram in Settings |
| Duplicate alerts | `signals_dedupe_idx` present; scanner replicas = 1 | Set replicas to 1 |

## Costs (estimates; confirm on each provider's pricing page)

| Item | Monthly |
|---|---|
| Railway (web, scanner, Postgres) | about $10 to $25 in usage |
| OANDA API | $0 with the owners' account |
| Massive Basic | $0 |
| Resend | $0 at this volume (confirm current free tier) |
| Telegram | $0 |
| Uptime monitor | $0 free tier |
| Domain | about $1 to $2 per month amortized |
