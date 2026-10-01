# Auth and Security

## Access model

- Invite only. An email must be in `allowlist` to sign in. There is no sign-up page.
- Sign-in by email magic link (Auth.js v5, Resend provider). Links expire after 15 minutes and work once.
- Sessions: database sessions, 30-day rolling expiry, `httpOnly`, `secure`, `sameSite=lax` cookies.
- Roles: `owner` and `admin`. The first admin comes from the seed. Admins manage the allowlist and roles.
- Deactivating a user deletes their sessions immediately and stops their notifications.

## Authorization

- Every route handler and server action checks session, active flag, and role.
- Owners can read all signals, levels, stocks, and history, and can write only their own preferences, broker choice, and holdings.
- Admin writes are audit logged with before and after values.

## Secrets

| Secret | Lives in | Never |
|---|---|---|
| `OANDA_API_TOKEN`, `OANDA_ACCOUNT_ID` | scanner env | In the web service or the browser |
| `MASSIVE_API_KEY` | scanner env | In the web service or the browser |
| `DATABASE_URL` | both services | In client bundles |
| `AUTH_SECRET`, `RESEND_API_KEY` | web env (Resend key also in scanner for email alerts) | In client bundles |
| `VAPID_PRIVATE_KEY` | scanner env (and web if the web sends test pushes directly) | In client bundles |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` | web and scanner env | In client bundles |

Rotate any key immediately if it appears in a log, commit, or screenshot.

## No trading credentials

The portal stores no broker logins, passwords, or API keys for any broker other than the OANDA data token, and that token is used only to read prices. Code that places orders is out of scope (see `18-compliance-guardrails.md`).

## Web hardening

- Content Security Policy restricting scripts to self; allow the chart library bundle and Resend images only as needed.
- `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` limited to notifications.
- Rate limit sign-in requests: 5 per email per 15 minutes, 20 per IP per hour.
- All mutations are server actions or POST routes with CSRF protection from Auth.js and same-origin checks.
- `robots.txt` disallows all; pages send `X-Robots-Tag: noindex`.

## Data protection

- Railway Postgres with daily backups enabled (confirm backup availability and retention on the chosen Railway plan during setup).
- No personal financial account data is stored. Holdings contain ticker, price, and date only.
- Logs never include tokens, full push subscription keys, or email magic links.

## Audit log

Recorded actions: rule version saved, rule approved, override set, instrument added or toggled, broker created, updated, or deleted, user added, role changed, user deactivated, signal invalidated. The Settings > Rules history panel and a simple admin audit view read from it.
