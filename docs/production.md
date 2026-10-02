# Production and the paper run

This is Phase 8 (spec 19): set up `portal-production`, then run it for 4 to 8 weeks as a paper run with no money at risk (spec 17). It starts only after the staging run in `docs/staging.md` is signed off on its checklist issue.

Production is set up the same way as staging. This guide covers what is different, then the runbook walkthrough and the weekly paper-run review.

Keys and secrets go into Railway's variables only. Never paste them into chat, GitHub, email, or a document.

## 1. What differs from staging

| | Staging | Production |
|---|---|---|
| Railway project | `portal-staging` | `portal-production` |
| Deploys from | `main` | `production` |
| Domain | Railway domain or `staging.` | The owners' domain, for example `desk.example.com` |
| `OANDA_ENV` | `practice` | Whatever the owners' OANDA account is: `live` for a live account, `practice` for a practice one |
| OANDA token | Practice token | A token from the owners' account |
| Telegram bot | Staging bot | **A separate bot.** A bot can point at only one webhook, so staging and production each need their own |
| Secrets | | **New ones.** Make a new `AUTH_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, and push key pair; never copy staging's |
| Postgres | Backups on | Backups on, and a restore tested once (step 4) |

Everything else (Resend, Massive, the variable table, the two services and their `railway.json` files, one scanner replica) is the same as in `docs/staging.md` sections 2 and 3.

**About the OANDA token.** OANDA tokens are not read-only; the token could place trades if something used it that way. The portal never does: the scanner only reads candles and prices, there is no order code anywhere (CLAUDE.md rule 7), and the token lives only on the scanner service. Keep it that way: never put it on the web service and never share it.

## 2. Set up `portal-production`

1. Follow `docs/staging.md` sections 2 and 3 in a new project called `portal-production`, with the differences above.
2. **Deploy branch.** Point both services at the `production` branch. Turn on "Wait for CI".
3. **Domain.** In the web service, Settings, Networking, add the custom domain and create the DNS record Railway shows at your domain registrar. When Railway shows the certificate as active, set `APP_URL` to `https://<domain>` on both services and redeploy web (this also points the Telegram bot at the new address).
4. **Email.** Use the Resend domain already verified for staging, or verify the production domain the same way. Set `EMAIL_FROM` on that domain.
5. **First admin.** Set `SEED_ADMIN_EMAIL`. After the first deploy, sign in and add the owners in Settings, Users.
6. **Uptime monitor.** Add a second check on `https://<domain>/api/health` every 5 minutes, alerting Jana.

## 3. Release flow

1. Changes merge to `main` and deploy to staging.
2. After checking staging, open a pull request from `main` into `production`, let CI pass, and merge it. Railway deploys production.
3. Rule changes need no deploy; they are data, made in Settings, Rules on production itself.

To roll back, open the service in Railway, choose the previous successful deployment, and redeploy it. For the web service, a rollback does not undo migrations, so a release with a migration is rolled forward with a fix instead.

## 4. First-week checks

- [ ] web deploy log: migrations, `seed-admin`, `telegram-webhook: registered for https://<domain>`, `heartbeat check started`
- [ ] scanner log: `scheduler starting`, no "skipped: ... not set" lines
- [ ] Health page: heartbeat fresh, every pair updating while forex is open
- [ ] Every owner has signed in, accepted the notice, chosen a broker, and received a test notification on each channel
- [ ] Backup restore test: in Railway, restore last night's Postgres backup into a new temporary database, check that it has the signals and users, then delete it

## 5. Runbook walkthrough

Walk through spec 16's runbook together once production is up, doing each step for real where it is safe:

| Practice | How |
|---|---|
| Read the Health page | Heartbeat age, pair freshness, recent job runs, and what each colour means |
| Scanner stopped | Remove the scanner's active deployment. Within about 6 minutes admins and `OPS_ALERT_EMAIL` get "Health alert: scanner heartbeat is late". Redeploy; within 5 minutes they get "Resolved" |
| Restart a service | In Railway, the service's deployment menu, Restart |
| Roll back a deploy | Section 3 above. Practise on the scanner, then redeploy the latest |
| Rerun a missed stock scan | `railway ssh --service scanner python -m scanner.jobs.stock_eod --date YYYY-MM-DD` |
| One pair stale | Check OANDA's status page and the pair's settings in Settings, Pairs; alerts for that pair resume on their own |
| Sunday evening | All forex shows stale until the first bar completes at 17:15 New York; nothing to do |
| An owner gets no push | Settings, Notifications shows the state; on iPhone the portal must be opened from the Home Screen |
| Telegram silent | Settings, Notifications: reconnect Telegram. If every owner is affected, check the web deploy log's `telegram-webhook` line |
| Duplicate alerts | Scanner replicas must be 1. The scanner also holds a database lock, so a second copy waits instead of running |

## 6. The paper run

Duration: 4 to 8 weeks, agreed with the owners before it starts. No money is at risk: the owners watch the signals and do not trade them, or trade them only on paper.

**Each week**, run the review and go through it together:

```
railway ssh --service scanner python -m scanner.ops.weekly_review
```

It covers the last 7 days:

- signals created, by strategy and pair
- outcomes of the signals that closed: win rate, net pips, pips per trade, and profit factor, with the same definitions as the backtest and the History page
- alerts sent, by channel and per owner per trading day
- for the 3/8 system, each indicator's evidence in closed signals: how often it fired, and the win rate and pips per trade when it did, with provisional rules listed first
- every note and every signal marked invalid, with who wrote it

Add `--since YYYY-MM-DD` (the first day of the paper run) to see everything so far, which is what to use when deciding on a provisional rule. Weekly numbers are small; a rule needs many signals before its numbers mean much.

**When an owner disagrees with a signal**, an admin opens it and adds a note with the reason (or marks it invalid if it should never have fired). The note appears in the next review.

**Exit criteria** (spec 17):

- [ ] The owners are comfortable with how many alerts arrive and how good they are
- [ ] Each provisional rule has enough evidence to approve, change, or disable it in Settings, Rules

When both are met, the paper run ends and the owners decide whether to trade from the signals. Nothing in the portal changes at that point: it still only suggests trades.
