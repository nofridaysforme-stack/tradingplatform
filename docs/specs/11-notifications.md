# Notifications

## Channels

| Channel | How | Setup by owner | Notes |
|---|---|---|---|
| Web push | VAPID web push from the worker with pywebpush | Allow notifications in the installed app | On iPhone, the portal must be added to the Home Screen from Safari before notifications can be enabled. The portal shows an install guide when it detects iOS Safari without the installed app. |
| Email | Resend | Nothing beyond sign-in email | Always available as the fallback |
| Telegram | Telegram Bot API `sendMessage` | Tap "Connect Telegram", which opens `https://t.me/<bot>?start=<link_token>`; the bot stores the chat id | Fastest and most reliable on phones; no carrier registration needed |

SMS is out of scope. US carrier registration (A2P 10DLC) takes weeks and adds fees, and the three channels above cover the need.

## What triggers a notification

| Kind | When | Default |
|---|---|---|
| signal | New 3/8 or Fibonacci Pivot signal | On |
| update | Fibonacci Pivot confirmation or reset reached; any signal closes | On (owner can turn off updates) |
| digest | Evening stock digest of newly trend-confirmed stocks | On |
| holding | A holding reached its sales target or its 20-session horizon | On |
| health | Worker or data problem | Admins only |
| test | Owner presses "Send test notification" | Manual |

## Filtering per owner

A notification is sent to an owner on a channel only if:
1. The owner is active.
2. The channel is in the owner's `channels`.
3. The strategy is in the owner's `strategies`.
4. The instrument is in `instrument_ids`, or that list is empty.
5. The current time is outside the owner's quiet hours, unless the kind is `health`.

During quiet hours, signal notifications are not sent later; they are marked `skipped` because a stale intraday alert can mislead. The signal still appears in the portal.

## Message templates

All templates are plain text with the same structure. No em dashes.

Signal (push and Telegram):
```
Title: Long EUR/USD (3/8 Formula)
Body:  Entry 1.08430  Stop 1.08180  Target 1.09040
       Reward to risk 2.4. Pivot, engulfing, 61.8% Fib.
       Prices adjusted for Broker A.
Link:  https://<portal>/signals/<id>
```

If the signal uses a provisional indicator, add the line: `Includes a provisional rule.`

Fibonacci Pivot signal body uses the ladder:
```
Break 1.09250 crossed. Stop 1.08700 (pivot). Target 1.10140 (take profit).
```

Update:
```
Title: EUR/USD long hit target
Body:  +63 pips. Closed 10:45 New York.
```

Stock digest (email and Telegram):
```
Subject: 4 stocks confirmed their trend today
Body:    Table of ticker, close, APR 20-day, APR 50-day, link to each stock page.
```

Email versions use a simple HTML layout matching the portal's tokens, with a plain-text alternative.

## Delivery

1. The dispatcher inserts one `notifications` row per owner per channel with status `queued`.
2. Sends run concurrently with a 10-second timeout per call.
3. Failures retry up to 3 times at 5, 20, and 60 seconds.
4. Web push responses 404 or 410 delete the subscription.
5. Status becomes `sent`, `failed`, or `skipped` with the error stored.

Target: notifications sent within 30 seconds of signal creation; end-to-end within 90 seconds of the bar close.

## Web push setup

- Generate VAPID keys once; store `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` (a `mailto:` address) in both services' environment.
- `public/manifest.webmanifest` with name, icons (192, 512, maskable), `display: standalone`, theme colors from the design tokens.
- `public/sw.js` handles `push` (show notification with title, body, icon, `data.url`) and `notificationclick` (focus or open `data.url`).
- Subscribe only after a user taps "Turn on notifications" (required by Safari).
- `POST /api/push/subscribe` stores the subscription; `POST /api/push/unsubscribe` removes it.

## Telegram setup

- Create a bot with BotFather; store `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BOT_USERNAME`.
- `POST /api/telegram/webhook` (secret path segment plus `X-Telegram-Bot-Api-Secret-Token` header) receives `/start <link_token>`, matches the token, stores `chat_id`, replies "Connected. You will receive trade alerts here."
- Owners can disconnect in Settings, which clears the link and sends a goodbye message.

## Health alerts

Sent to admins and to `OPS_ALERT_EMAIL` through email and Telegram:
- Worker heartbeat older than 5 minutes
- No new completed bar for an enabled pair for 30 minutes while the market is open
- Provider authentication errors
- A job failing three runs in a row

Health alerts repeat at most once per hour per condition and send a "Resolved" message when the condition clears.

The scanner checks these every 5 minutes. A stopped scanner cannot report its own late heartbeat, so the web service checks the heartbeat every minute and sends that alert itself, sharing the same alert state; the scanner sends "Resolved" when it returns.
