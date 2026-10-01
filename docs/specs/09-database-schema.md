# Database Schema

Postgres. Migrations are plain SQL in `/db/migrations`, applied with dbmate. This file is the schema of record; the first migration implements it. All timestamps are `timestamptz` in UTC. Prices are `numeric(18,8)`.

## Enums

```sql
CREATE TYPE user_role        AS ENUM ('owner', 'admin');
CREATE TYPE strategy_key     AS ENUM ('three_eight', 'fib_pivot', 'stocks');
CREATE TYPE rule_kind        AS ENUM ('indicator', 'gate', 'plan', 'filter', 'lifecycle');
CREATE TYPE rule_status      AS ENUM ('approved', 'provisional');
CREATE TYPE direction        AS ENUM ('long', 'short');
CREATE TYPE signal_state     AS ENUM ('open', 'confirmed', 'target_hit', 'stop_hit', 'expired', 'invalidated', 'ambiguous');
CREATE TYPE channel_kind     AS ENUM ('webpush', 'email', 'telegram');
CREATE TYPE delivery_status  AS ENUM ('queued', 'sent', 'failed', 'skipped');
CREATE TYPE level_set        AS ENUM ('daily', 'weekly', 'monthly', 'prev_day', 'fib_pivot');
CREATE TYPE econ_impact      AS ENUM ('high', 'medium', 'low');
CREATE TYPE screen_status    AS ENUM ('qualified', 'trend_established', 'trend_confirmed');
```

## People and access

```sql
CREATE TABLE users (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email           text UNIQUE NOT NULL,
  name            text,
  role            user_role NOT NULL DEFAULT 'owner',
  active          boolean NOT NULL DEFAULT true,
  timezone        text NOT NULL DEFAULT 'America/New_York',
  active_broker_id uuid,
  acknowledged_notice_at timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- Auth.js tables (accounts, sessions, verification_tokens) follow the Auth.js Postgres adapter schema.

CREATE TABLE allowlist (
  email       text PRIMARY KEY,
  added_by    uuid REFERENCES users(id),
  added_at    timestamptz NOT NULL DEFAULT now()
);
```

## Instruments and brokers

```sql
CREATE TABLE instruments (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol        text UNIQUE NOT NULL,          -- 'EUR/USD'
  provider_code text NOT NULL,                 -- 'EUR_USD'
  asset_class   text NOT NULL DEFAULT 'forex',
  pip_size      numeric(12,8) NOT NULL,
  display_decimals smallint NOT NULL,
  enabled       boolean NOT NULL DEFAULT true,
  sort_order    smallint NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE brokers (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text UNIQUE NOT NULL,
  platform_url_template text,                  -- e.g. 'https://trade.example.com/?symbol={symbol}'
  notes           text,
  active          boolean NOT NULL DEFAULT true,
  created_at      timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE users ADD CONSTRAINT users_active_broker_fk
  FOREIGN KEY (active_broker_id) REFERENCES brokers(id) ON DELETE SET NULL;

CREATE TABLE broker_spreads (
  broker_id     uuid REFERENCES brokers(id) ON DELETE CASCADE,
  instrument_id uuid REFERENCES instruments(id) ON DELETE CASCADE,
  typical_spread_pips numeric(8,2) NOT NULL,
  symbol_override text,                        -- broker's own symbol if different
  PRIMARY KEY (broker_id, instrument_id)
);

CREATE TABLE market_holidays (
  day         date PRIMARY KEY,
  market      text NOT NULL,                   -- 'forex' or 'us_stocks'
  note        text
);
```

## Market data

```sql
CREATE TABLE candles (
  instrument_id uuid REFERENCES instruments(id) ON DELETE CASCADE,
  granularity   text NOT NULL,                 -- 'M15', 'D', 'W', 'M'
  ts            timestamptz NOT NULL,          -- bar open, UTC
  o numeric(18,8) NOT NULL, h numeric(18,8) NOT NULL,
  l numeric(18,8) NOT NULL, c numeric(18,8) NOT NULL,
  volume        integer NOT NULL DEFAULT 0,
  PRIMARY KEY (instrument_id, granularity, ts)
);

CREATE TABLE stock_tickers (
  ticker        text PRIMARY KEY,
  name          text,
  exchange      text,
  active        boolean NOT NULL DEFAULT true,
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE stock_daily_bars (
  ticker        text NOT NULL,
  session_date  date NOT NULL,
  o numeric(18,6) NOT NULL, h numeric(18,6) NOT NULL,
  l numeric(18,6) NOT NULL, c numeric(18,6) NOT NULL,
  volume        bigint NOT NULL,
  PRIMARY KEY (ticker, session_date)
);
CREATE INDEX stock_daily_bars_date_idx ON stock_daily_bars (session_date);

CREATE TABLE levels (
  instrument_id uuid REFERENCES instruments(id) ON DELETE CASCADE,
  trading_day   date NOT NULL,                 -- New York trading day the levels apply to
  set_kind      level_set NOT NULL,
  data          jsonb NOT NULL,                -- e.g. {"P":1.087,"R1":...} or the fib ladder
  computed_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (instrument_id, trading_day, set_kind)
);

CREATE TABLE econ_events (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  at          timestamptz NOT NULL,
  currency    char(3) NOT NULL,
  title       text NOT NULL,
  impact      econ_impact NOT NULL DEFAULT 'high',
  created_by  uuid REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX econ_events_at_idx ON econ_events (at);
```

## Rules

```sql
CREATE TABLE rule_definitions (
  key           text PRIMARY KEY,              -- 'three_eight.pivot_touch'
  strategy      strategy_key NOT NULL,
  kind          rule_kind NOT NULL,
  name          text NOT NULL,
  source        text NOT NULL,                 -- document reference
  current_version integer NOT NULL
);

CREATE TABLE rule_versions (
  key           text REFERENCES rule_definitions(key) ON DELETE CASCADE,
  version       integer NOT NULL,
  status        rule_status NOT NULL,
  enabled       boolean NOT NULL DEFAULT true,
  counts_toward_minimum boolean NOT NULL DEFAULT false,
  description   text NOT NULL,
  params_schema jsonb NOT NULL,                -- types, defaults, ranges, units
  params        jsonb NOT NULL,                -- chosen values
  change_note   text,
  created_by    uuid REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (key, version)
);

CREATE TABLE strategy_param_overrides (
  key           text REFERENCES rule_definitions(key) ON DELETE CASCADE,
  instrument_id uuid REFERENCES instruments(id) ON DELETE CASCADE,
  params        jsonb NOT NULL,                -- only overridden params
  updated_by    uuid REFERENCES users(id),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (key, instrument_id)
);

CREATE TABLE rule_config_revision (
  id            boolean PRIMARY KEY DEFAULT true CHECK (id),
  revision      bigint NOT NULL DEFAULT 1,
  updated_at    timestamptz NOT NULL DEFAULT now()
);
```

## Signals

```sql
CREATE TABLE signals (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy      strategy_key NOT NULL,
  instrument_id uuid REFERENCES instruments(id),
  direction     direction NOT NULL,
  state         signal_state NOT NULL DEFAULT 'open',
  bar_ts        timestamptz NOT NULL,          -- triggering bar open time
  trading_day   date NOT NULL,
  entry         numeric(18,8) NOT NULL,
  stop          numeric(18,8) NOT NULL,
  target        numeric(18,8) NOT NULL,
  alt_target    numeric(18,8),
  risk_pips     numeric(10,2) NOT NULL,
  reward_pips   numeric(10,2) NOT NULL,
  reward_risk   numeric(8,3) NOT NULL,
  indicator_count smallint,
  has_provisional boolean NOT NULL DEFAULT false,
  is_countertrend boolean NOT NULL DEFAULT false,
  range_mode    boolean NOT NULL DEFAULT false,
  version_set   jsonb NOT NULL,                -- {"three_eight.pivot_touch":1, ...}
  context       jsonb NOT NULL,                -- trend, levels used, swing data
  dedupe_key    text NOT NULL,
  closed_at     timestamptz,
  exit_price    numeric(18,8),
  result_pips   numeric(10,2),
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX signals_dedupe_idx ON signals (dedupe_key);
CREATE INDEX signals_open_idx ON signals (instrument_id) WHERE state IN ('open','confirmed');
CREATE INDEX signals_created_idx ON signals (created_at DESC);

CREATE TABLE signal_indicators (
  signal_id     uuid REFERENCES signals(id) ON DELETE CASCADE,
  key           text NOT NULL,
  version       integer NOT NULL,
  fired         boolean NOT NULL,
  counted       boolean NOT NULL,
  provisional   boolean NOT NULL,
  level_ref     text,
  detail        jsonb NOT NULL,
  PRIMARY KEY (signal_id, key)
);

CREATE TABLE signal_events (
  id            bigserial PRIMARY KEY,
  signal_id     uuid REFERENCES signals(id) ON DELETE CASCADE,
  at            timestamptz NOT NULL DEFAULT now(),
  kind          text NOT NULL,                 -- 'created','confirmed','reset_reached','target_hit','stop_hit','expired','invalidated'
  price         numeric(18,8),
  note          text
);
```

## Stocks

```sql
CREATE TABLE stock_screen_results (
  session_date  date NOT NULL,
  ticker        text NOT NULL,
  status        screen_status NOT NULL,
  close         numeric(18,6) NOT NULL,
  high_52w      numeric(18,6) NOT NULL,
  low_52w       numeric(18,6) NOT NULL,
  apr_52w       numeric(12,6) NOT NULL,
  close_5 numeric(18,6), close_10 numeric(18,6), close_20 numeric(18,6), close_50 numeric(18,6),
  acc_5 numeric(12,6), acc_10 numeric(12,6), acc_20 numeric(12,6), acc_50 numeric(12,6),
  apr_5 numeric(14,6), apr_10 numeric(14,6), apr_20 numeric(14,6), apr_50 numeric(14,6),
  consistent    boolean NOT NULL DEFAULT false,
  version_set   jsonb NOT NULL,
  PRIMARY KEY (session_date, ticker)
);

CREATE TABLE holdings (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid REFERENCES users(id) ON DELETE CASCADE,
  ticker        text NOT NULL,
  purchase_price numeric(18,6) NOT NULL,
  purchase_date date NOT NULL,
  expected_profit_pct numeric(6,2) NOT NULL DEFAULT 30,
  horizon_sessions smallint NOT NULL DEFAULT 20,
  closed        boolean NOT NULL DEFAULT false,
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now()
);
```

## Notifications

```sql
CREATE TABLE notification_prefs (
  user_id       uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  channels      channel_kind[] NOT NULL DEFAULT '{webpush,email}',
  strategies    strategy_key[] NOT NULL DEFAULT '{three_eight,fib_pivot,stocks}',
  instrument_ids uuid[],                       -- null means all enabled
  quiet_start   time,                          -- in the user's timezone
  quiet_end     time,
  include_updates boolean NOT NULL DEFAULT true,  -- confirmation, outcome messages
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE push_subscriptions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid REFERENCES users(id) ON DELETE CASCADE,
  endpoint      text UNIQUE NOT NULL,
  p256dh        text NOT NULL,
  auth          text NOT NULL,
  user_agent    text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  last_success_at timestamptz
);

CREATE TABLE telegram_links (
  user_id       uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  chat_id       bigint,
  link_token    text UNIQUE,
  linked_at     timestamptz
);

CREATE TABLE notifications (
  id            bigserial PRIMARY KEY,
  user_id       uuid REFERENCES users(id) ON DELETE CASCADE,
  signal_id     uuid REFERENCES signals(id) ON DELETE SET NULL,
  kind          text NOT NULL,                 -- 'signal','update','digest','health','test'
  channel       channel_kind NOT NULL,
  status        delivery_status NOT NULL DEFAULT 'queued',
  attempts      smallint NOT NULL DEFAULT 0,
  error         text,
  payload       jsonb NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  sent_at       timestamptz
);
```

## Operations

```sql
CREATE TABLE job_runs (
  id            bigserial PRIMARY KEY,
  job           text NOT NULL,                 -- 'forex_bar_close','forex_day_roll','stock_eod','heartbeat','backfill'
  started_at    timestamptz NOT NULL DEFAULT now(),
  finished_at   timestamptz,
  ok            boolean,
  detail        jsonb
);
CREATE INDEX job_runs_job_started_idx ON job_runs (job, started_at DESC);

CREATE TABLE worker_heartbeat (
  id            boolean PRIMARY KEY DEFAULT true CHECK (id),
  at            timestamptz NOT NULL,
  version       text
);

CREATE TABLE audit_log (
  id            bigserial PRIMARY KEY,
  at            timestamptz NOT NULL DEFAULT now(),
  user_id       uuid REFERENCES users(id),
  action        text NOT NULL,                 -- 'rule.update','rule.approve','instrument.add', ...
  target        text,
  before        jsonb,
  after         jsonb
);
```

## Retention

| Table | Keep |
|---|---|
| candles M15 | 2 years (backtests fetch deeper history directly from OANDA) |
| candles D, W, M | Indefinitely |
| stock_daily_bars | 400 sessions |
| stock_screen_results | 2 years |
| signals and children | Indefinitely |
| notifications | 180 days |
| job_runs | 90 days |

A nightly `retention` job deletes expired rows.

## Seed migration

Seeds: the seven instruments, the rule definitions and version 1 rows from specs 06 to 08, `rule_config_revision`, `worker_heartbeat`, and the first admin email in `allowlist` (from an environment variable at seed time).
