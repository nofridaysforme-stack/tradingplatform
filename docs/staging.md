# Staging setup and the 10-day run

This is the step-by-step for Phase 7 (spec 19): set up `portal-staging` on Railway, connect each outside service, then run the 10-day acceptance check from spec 17. Spec 16 has the reference tables; this guide is the order to do things in.

Keys and secrets go into Railway's variables only. Never paste them into chat, GitHub, email, or a document.

## 1. Accounts to open first

Open these in the business's name (spec 16) and add Jana as a collaborator.

| Account | What you need from it |
|---|---|
| Railway | A project called `portal-staging`, connected to the GitHub repository |
| OANDA | A practice account, its account ID, and an API token (staging uses `OANDA_ENV=practice`) |
| Massive | An API key on the Basic plan |
| Resend | An API key and a verified sending domain (Resend shows the DNS records to add) |
| Telegram | A bot made with BotFather: its token and its username |
| Uptime monitor | A free Better Stack or UptimeRobot account |

The portal works without the OANDA, Massive, push, email, or Telegram settings; each part simply stays off until its keys are added. The 10-day run needs all of them.

## 2. Create the Railway services

In `portal-staging`:

1. **Postgres.** Add a Postgres database. Turn on backups.
2. **web.** Add a service from the GitHub repository.
   - Settings, Source: root directory `/`, config file path `/apps/web/railway.json`.
   - Settings, Networking: generate a domain (or attach `staging.<your domain>`).
   - The config file sets the Dockerfile, the pre-deploy command (`/app/db/migrate.sh`), the start command, and a health check on `/sign-in`.
3. **scanner.** Add a second service from the same repository.
   - Settings, Source: root directory `/services/scanner`, config file path `/services/scanner/railway.json`.
   - No public domain. Keep it at **one replica**.
   - The scanner holds a database lock while it runs, so during a redeploy the new copy waits until the old one has stopped. It never runs the schedule twice.
4. **Deploys.** For both services: deploy from `main`, and turn on "Wait for CI" so a red build never deploys.

If Railway rejects a field in either `railway.json`, set the same value in the service's settings page; the file and the settings page hold the same options.

## 3. Variables

Use Railway's reference variable for the database (`${{Postgres.DATABASE_URL}}`) so it updates itself. `APP_URL` is the web service's public address, starting with `https://`.

| Variable | web | scanner | How to get it |
|---|---|---|---|
| `DATABASE_URL` | yes | yes | Reference variable |
| `APP_URL` | yes | yes | The web domain, for example `https://staging.example.com` |
| `AUTH_SECRET` | yes | | Run `openssl rand -base64 32` on your computer |
| `SEED_ADMIN_EMAIL` | yes | | The first admin's email; added to the allowlist on each deploy |
| `RESEND_API_KEY` | yes | yes | Resend dashboard |
| `EMAIL_FROM` | yes | yes | For example `Trading desk <alerts@example.com>`, on the verified domain |
| `OANDA_API_TOKEN` | | yes | OANDA account settings |
| `OANDA_ACCOUNT_ID` | | yes | OANDA account settings |
| `OANDA_ENV` | | yes | `practice` |
| `MASSIVE_API_KEY` | | yes | Massive dashboard |
| `VAPID_PUBLIC_KEY` | yes | yes | See below |
| `VAPID_PRIVATE_KEY` | | yes | See below |
| `VAPID_SUBJECT` | | yes | `mailto:` plus the ops address |
| `TELEGRAM_BOT_TOKEN` | yes | yes | From BotFather |
| `TELEGRAM_BOT_USERNAME` | yes | | The bot's username, without the `@` |
| `TELEGRAM_WEBHOOK_SECRET` | yes | | Run `openssl rand -hex 24` on your computer |
| `OPS_ALERT_EMAIL` | | yes | Where health alerts go besides the admins |
| `LOG_LEVEL` | yes | yes | `info` |

**Push keys.** Make the pair once per environment. With the Railway command line installed and linked to the project:

```
railway ssh --service scanner python -m scanner.ops.vapid_keys
```

or, on a computer with the repository: `cd services/scanner && uv run python -m scanner.ops.vapid_keys`. Copy the two printed values straight into the variables and close the terminal. A new pair means every device has to turn notifications on again.

**Telegram webhook.** Nothing to run. Every web deploy points the bot at `APP_URL` once the three Telegram variables and `APP_URL` are set; the web deploy log shows `telegram-webhook: registered`. After changing the domain or the secret, redeploy web.

## 4. First deploy checks

1. **web deploy log** shows the migrations, then `seed-admin: admin email is on the allowlist`, then a `telegram-webhook` line.
2. **scanner log** shows `schema ok`, `notification channels`, and `scheduler starting`. A line saying a job was skipped because a key is not set means that variable is missing.
3. **Sign in** at the web domain with `SEED_ADMIN_EMAIL`. Open Health: the heartbeat is under a minute old.
4. **Owners.** In Settings, Users, add each owner's email. Each owner then signs in, chooses a broker, opens Settings, Notifications, turns on push (on iPhone, add the portal to the Home Screen first), connects Telegram, and presses **Send test notification**.
5. **Uptime monitor.** Add a check on `https://<web domain>/api/health` every 5 minutes, alerting Jana. It reports a problem when the database is unreachable, the scanner's heartbeat is over 5 minutes old, or a pair stops updating while forex is open. Until the OANDA key is set it reports `pairs_stale` during market hours; that is expected.

## 5. The 10-day run

Start counting on the first full forex trading day after every key is in. Each day, an admin opens Health and the dashboard. Note anything odd as a comment on the staging checklist issue.

At the end, run the report:

```
railway ssh --service scanner python -m scanner.ops.staging_report --days 10
```

It checks what the database can prove and prints "Result: all automatic checks passed" or the reasons it is not ready:

- ten complete forex trading days in the window
- every 15-minute bar close ran (retries count)
- no job failed or died mid-run
- no gap of over 20 minutes in the scanner's runs
- every test notification was delivered within 90 seconds

Use `--since YYYY-MM-DD` to restart the count after a fix. The report also lists what needs a person to confirm:

1. **Rules.** Every rule shows in Settings, Rules with the right status, parameters, and source reference.
2. **Rule change.** Change one parameter on staging, check that the next bar's signals use the new version, and that the change appears in the audit log. Change it back.
3. **Failure drill.** Stop the scanner for 10 minutes (remove its active deployment in Railway), confirm the alert, redeploy it, and confirm the "Resolved" message.

When everything passes, record the sign-off on the checklist issue. Phase 8 (production) starts after that.
