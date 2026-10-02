# API Contracts

The web app reads Postgres directly from server components and route handlers. These routes exist for client-side polling, the service worker, Telegram, and health checks. All routes except `/api/health` and the Telegram webhook require a signed-in, active, allowlisted user. Admin-only routes check `role = 'admin'`.

Responses are JSON. Errors use `{ "error": { "code": "string", "message": "plain sentence" } }` with the right HTTP status. Inputs are validated with zod.

## Read endpoints (polled every 30 seconds while visible)

| Method and path | Returns |
|---|---|
| `GET /api/signals?state=open,confirmed&strategy=&instrument=` | Signal list items with broker-adjusted prices for the caller |
| `GET /api/signals/:id` | Full signal payload, indicators, gates, events, candles for the chart window, adjusted prices |
| `GET /api/levels?instrument=EUR/USD&day=` | All level sets for that pair and day, plus last price |
| `GET /api/market-status` | Forex open or closed, session (see T8 in spec 20), trading window state, New York time, stale pairs. The worker computes these with each heartbeat (`worker_heartbeat.market`); the portal only displays them |
| `GET /api/stocks/results?session=&status=&q=&sort=&page=` | Paginated screen results |
| `GET /api/stocks/:ticker` | Bars (6 months), latest result, status history |
| `GET /api/history?filters...` | Paginated closed signals plus summary metrics for the filter |
| `GET /api/history/export.csv?filters...` | CSV download |
| `GET /api/health/detail` | Heartbeat, per-pair last bar, job runs, delivery stats (admin) |

### Signal list item

```json
{
  "id": "uuid",
  "strategy": "three_eight",
  "instrument": "EUR/USD",
  "direction": "long",
  "state": "open",
  "created_at": "2026-10-05T08:15:04Z",
  "indicator_count": 3,
  "indicators_fired": ["three_eight.pivot_touch", "three_eight.candlestick", "three_eight.fibonacci"],
  "has_provisional": false,
  "confluence": false,
  "reference": {"entry": "1.08420", "stop": "1.08190", "target": "1.09050", "reward_risk": 2.74},
  "adjusted": {"broker": "Broker A", "entry": "1.08430", "stop": "1.08180", "target": "1.09040", "reward_risk": 2.44}
}
```

## Mutations (server actions, with matching POST routes for testability)

| Action | Who | Effect |
|---|---|---|
| `setActiveBroker(brokerId)` | Owner | Updates `users.active_broker_id` |
| `saveNotificationPrefs(prefs)` | Owner | Upserts `notification_prefs` |
| `sendTestNotification()` | Owner | Queues a `test` notification on each enabled channel |
| `createHolding`, `updateHolding`, `closeHolding` | Owner (own rows) | Holdings CRUD |
| `upsertBroker`, `deleteBroker`, `upsertBrokerSpreads` | Admin | Broker CRUD; audit logged |
| `upsertInstrument`, `toggleInstrument` | Admin | Instruments; triggers backfill when added; audit logged |
| `saveRuleVersion(key, params, description, note)` | Admin | New `rule_versions` row, bumps `rule_definitions.current_version` and `rule_config_revision`; audit logged |
| `approveRule(key, note)` | Admin | New version with status `approved`; same side effects |
| `setRuleOverride(key, instrumentId, params)` | Admin | Upserts override, bumps revision; audit logged |
| `createEconEvent`, `deleteEconEvent` | Admin | Econ events |
| `invalidateSignal(id, reason)`, `addSignalNote(id, note)` | Admin | Signal events; audit logged |
| `addAllowlistEmail`, `setUserRole`, `deactivateUser` | Admin | Access management; audit logged |

Parameter values are validated against the rule's `params_schema` (type, min, max, enum) on the server before saving.

## Push and Telegram

| Method and path | Purpose |
|---|---|
| `GET /api/push/public-key` | Returns the VAPID public key |
| `POST /api/push/subscribe` | Body: PushSubscription JSON. Stores it for the caller. |
| `POST /api/push/unsubscribe` | Body: `{ endpoint }` |
| `POST /api/telegram/link` | Creates a `link_token` and returns the deep link |
| `POST /api/telegram/webhook/:secret` | Telegram updates; verifies the secret token header |

## Health (public, minimal)

`GET /api/health` returns `200 {"ok": true}` when the database is reachable, the heartbeat is fresh (under 5 minutes), and no enabled pair is stale while the market is open. Otherwise `503` with `{"ok": false, "reasons": ["heartbeat_stale"]}`. No signal or price data is exposed. An external uptime monitor polls this every 5 minutes.

## Worker

The worker exposes no public HTTP API. It writes to Postgres and sends notifications. For Railway health checks it serves `GET /healthz` on an internal port returning 200 while its scheduler loop is alive.
