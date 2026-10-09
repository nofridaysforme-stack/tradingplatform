-- migrate:up

-- The stock momentum system (spec 08, revised 2026-10-08): momentum test, watch list, a buy
-- on 3 of 5 indicators, and exits by a fixed stop, a trailing stop, or 3 of 5 sell indicators.

-- 1. New rules, version 1. Each default lives once, in params_schema.

CREATE TEMP TABLE seed_rules (
  key         text,
  kind        rule_kind,
  name        text,
  source      text,
  status      rule_status,
  enabled     boolean,
  counts      boolean,
  description text,
  schema      jsonb
);

INSERT INTO seed_rules VALUES
('stocks.momentum', 'gate', 'Momentum',
 'Owners 2026-10-08: 455% with the 10 day, so 35% in 20 days; 5 Line Bar', 'provisional', true, false,
 'The period-day APR from the five line chart is at least projection_pct / 100 / horizon_sessions times the trader year (0.35 / 20 x 260 = 455 percent).',
 '{"period": {"type": "sessions", "default": 10, "min": 5, "max": 50},
   "projection_pct": {"type": "percent", "default": 35, "min": 1, "max": 1000},
   "horizon_sessions": {"type": "sessions", "default": 20, "min": 1, "max": 260}}'),

('stocks.watch', 'lifecycle', 'Watch list',
 'Owners 2026-10-08: catch the support within the 10% pullback; spec 08 interpretation', 'provisional', true, false,
 'A qualified stock that passes the momentum test joins the watch list. It stays while it is still qualified, for up to watch_sessions after it last passed, and leaves when bought.',
 '{"watch_sessions": {"type": "sessions", "default": 10, "min": 1, "max": 60},
   "require_trend_confirmed": {"type": "boolean", "default": false}}'),

('stocks.ind_candle', 'indicator', 'Price and candle',
 'Owners 2026-10-08: price is the number one indicator, with bullish candles on support', 'provisional', true, true,
 'Buy: a bullish pattern completes on a session whose close is inside the pullback zone. Sell: a bearish pattern completes. TA-Lib patterns on daily bars.',
 '{"bullish": {"type": "list", "default": ["hammer", "inverted_hammer", "engulfing", "piercing", "morning_star", "harami", "dragonfly_doji"],
               "options": ["hammer", "inverted_hammer", "engulfing", "piercing", "morning_star", "harami", "dragonfly_doji"]},
   "bearish": {"type": "list", "default": ["engulfing", "dark_cloud_cover", "hanging_man", "shooting_star", "evening_star", "harami"],
               "options": ["engulfing", "dark_cloud_cover", "hanging_man", "shooting_star", "evening_star", "harami"]}}'),

('stocks.ind_macd', 'indicator', 'MACD crossover',
 'Owners 2026-10-08: the crossing of the 2 MACD lines', 'approved', true, true,
 'Buy: the MACD line crosses above its signal line. Sell: it crosses below.',
 '{"fast": {"type": "sessions", "default": 12, "min": 2, "max": 100},
   "slow": {"type": "sessions", "default": 26, "min": 3, "max": 200},
   "signal": {"type": "sessions", "default": 9, "min": 2, "max": 100}}'),

('stocks.ind_pivot', 'indicator', 'Pivot point crossover',
 'Owners 2026-10-08: the pivot point as a line, with a 3 day average crossover', 'approved', true, true,
 'Each session''s pivot is (high + low + close) / 3. Buy: the pivot line hooks above its average of the last average_sessions pivots. Sell: it hooks below.',
 '{"average_sessions": {"type": "sessions", "default": 3, "min": 2, "max": 50}}'),

('stocks.ind_rsi', 'indicator', 'RSI',
 'Owners 2026-10-08: RSI crossing above 30; sell level is a spec 08 interpretation', 'provisional', true, true,
 'Buy: RSI crosses above buy_level. Sell: RSI crosses below sell_level.',
 '{"period": {"type": "sessions", "default": 14, "min": 2, "max": 100},
   "buy_level": {"type": "integer", "default": 30, "min": 1, "max": 99},
   "sell_level": {"type": "integer", "default": 70, "min": 1, "max": 99}}'),

('stocks.ind_stoch', 'indicator', 'Stochastics',
 'Owners 2026-10-08: Stochastics crossing over the 20; sell level is a spec 08 interpretation', 'provisional', true, true,
 'Slow %K. Buy: %K crosses above buy_level. Sell: %K crosses below sell_level.',
 '{"k_period": {"type": "sessions", "default": 14, "min": 2, "max": 100},
   "k_slowing": {"type": "sessions", "default": 3, "min": 1, "max": 20},
   "d_period": {"type": "sessions", "default": 3, "min": 1, "max": 20},
   "buy_level": {"type": "integer", "default": 20, "min": 1, "max": 99},
   "sell_level": {"type": "integer", "default": 80, "min": 1, "max": 99}}'),

('stocks.buy_vote', 'gate', 'Buy vote',
 'Owners 2026-10-08: 3 of 5 indicators, a window of 3 trading days', 'approved', true, false,
 'A watched stock is bought when at least min_votes different buy indicators fired within the last window_sessions sessions and the close is inside the pullback zone.',
 '{"min_votes": {"type": "integer", "default": 3, "min": 1, "max": 5},
   "window_sessions": {"type": "sessions", "default": 3, "min": 1, "max": 20}}'),

('stocks.projection', 'plan', 'Projection',
 'Owners 2026-10-08: 35% is a price projection; Entry Points and Sales Targets', 'approved', true, false,
 'Projected price = entry x (1 + projection_pct) within horizon_sessions (from the Momentum rule), with daily and weekly targets. A guide, not an exit.',
 '{}'),

('stocks.stop_loss', 'plan', 'Stop loss',
 'Owners 2026-10-08: 5% if the trade goes against us', 'approved', true, false,
 'Until the trailing stop starts, a close at or below entry x (1 - stop_pct) is a stop exit.',
 '{"stop_pct": {"type": "percent", "default": 5, "min": 0.5, "max": 50}}'),

('stocks.trailing_stop', 'plan', 'Trailing stop',
 'Owners 2026-10-08: after it has gained 10%, a trailing stop set at 5%', 'approved', true, false,
 'Once the highest close since entry is trail_after_pct above entry, the stop is trail_pct below the highest close and never falls. A close at or below it is a trailing stop exit.',
 '{"trail_after_pct": {"type": "percent", "default": 10, "min": 0, "max": 500},
   "trail_pct": {"type": "percent", "default": 5, "min": 0.5, "max": 50}}'),

('stocks.sell_vote', 'gate', 'Sell vote',
 'Owners 2026-10-08: ride the trend until the indicators give a sell; 3 of 5 is a spec 08 interpretation', 'provisional', true, false,
 'A sell signal exit when at least min_votes different sell indicators fired within the last window_sessions sessions.',
 '{"min_votes": {"type": "integer", "default": 3, "min": 1, "max": 5},
   "window_sessions": {"type": "sessions", "default": 3, "min": 1, "max": 20}}'),

('stocks.alert_watch', 'lifecycle', 'Watch list digest',
 'Spec 08 interpretation (alert timing not stated)', 'provisional', true, false,
 'One evening digest lists the stocks that joined the watch list that session, best momentum first, up to max_in_digest.',
 '{"max_in_digest": {"type": "integer", "default": 25, "min": 1, "max": 500}}'),

('stocks.alert_projection', 'lifecycle', 'Projection reached',
 'Spec 08 interpretation', 'provisional', true, false,
 'An information alert when a buy or a holding first closes at or above its projected price.',
 '{}'),

('stocks.alert_horizon', 'lifecycle', 'Horizon passed',
 'Spec 08 interpretation', 'provisional', false, false,
 'An information alert when horizon_sessions pass without reaching the projected price. Off by default.',
 '{}');

INSERT INTO rule_definitions (key, strategy, kind, name, source, current_version)
SELECT key, 'stocks', kind, name, source, 1 FROM seed_rules;

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT key, 1, status, enabled, counts, description, schema,
       COALESCE((SELECT jsonb_object_agg(p.key, p.value -> 'default')
                 FROM jsonb_each(schema) AS p), '{}'::jsonb),
       'Seeded from the owners'' instructions of 2026-10-08'
FROM seed_rules;

DROP TABLE seed_rules;

-- 2. Rules the funnel replaces get a switched-off version 2, so their history stays.
INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT key, 2, status, false, counts_toward_minimum, description, params_schema, params,
       'Replaced by the momentum system (decision 2026-10-08)'
FROM rule_versions
WHERE key IN ('stocks.sales_target', 'stocks.alert_new_confirmed',
              'stocks.alert_target_reached', 'stocks.alert_time_elapsed')
  AND version = 1;

UPDATE rule_definitions SET current_version = 2
WHERE key IN ('stocks.sales_target', 'stocks.alert_new_confirmed',
              'stocks.alert_target_reached', 'stocks.alert_time_elapsed');

UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();

-- 3. The funnel stage of each screened stock, and the day's indicator results.
ALTER TABLE stock_screen_results
  ADD COLUMN momentum  boolean NOT NULL DEFAULT false,
  ADD COLUMN watching  boolean NOT NULL DEFAULT false,
  ADD COLUMN indicators jsonb;

-- 4. Buys and their exits. A buy explains itself: the indicators that voted, the rule versions,
--    and whether a provisional rule voted (CLAUDE.md rule 3).
CREATE TABLE stock_signals (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker           text NOT NULL,
  buy_session      date NOT NULL,
  entry            numeric(18,6) NOT NULL,
  stop_initial     numeric(18,6) NOT NULL,
  projection       numeric(18,6) NOT NULL,
  projection_pct   numeric(8,2) NOT NULL,
  horizon_sessions smallint NOT NULL,
  state            text NOT NULL DEFAULT 'open'
                   CHECK (state IN ('open', 'stopped', 'trailing_stopped', 'sold')),
  trailing_active  boolean NOT NULL DEFAULT false,
  highest_close    numeric(18,6) NOT NULL,
  stop_now         numeric(18,6) NOT NULL,
  projection_session date,
  last_session     date NOT NULL,
  exit_session     date,
  exit_price       numeric(18,6),
  result_pct       numeric(12,6),
  votes            jsonb NOT NULL,
  exit_votes       jsonb,
  version_set      jsonb NOT NULL,
  has_provisional  boolean NOT NULL DEFAULT false,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (ticker, buy_session)
);
CREATE UNIQUE INDEX stock_signals_one_open_idx ON stock_signals (ticker) WHERE state = 'open';
CREATE INDEX stock_signals_buy_idx ON stock_signals (buy_session DESC);

CREATE TABLE stock_signal_events (
  id         bigserial PRIMARY KEY,
  signal_id  uuid NOT NULL REFERENCES stock_signals(id) ON DELETE CASCADE,
  session    date NOT NULL,
  kind       text NOT NULL,             -- 'bought','trailing_started','projection_reached','horizon_passed','stopped','trailing_stopped','sold'
  price      numeric(18,6),
  detail     jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (signal_id, kind)
);

-- 5. Holdings: a holding can name the buy it came from; new holdings project 35 percent. The
--    scanner writes where each open holding stands after every session (the portal only reads).
ALTER TABLE holdings
  ADD COLUMN signal_id uuid REFERENCES stock_signals(id) ON DELETE SET NULL,
  ADD COLUMN highest_close numeric(18,6),
  ADD COLUMN trailing_active boolean NOT NULL DEFAULT false,
  ADD COLUMN stop_now numeric(18,6),
  ADD COLUMN sell_reason text CHECK (sell_reason IN ('stopped', 'trailing_stopped', 'sold')),
  ADD COLUMN sell_session date,
  ADD COLUMN sell_price numeric(18,6),
  ADD COLUMN tracked_session date,
  ALTER COLUMN expected_profit_pct SET DEFAULT 35;

-- migrate:down

ALTER TABLE holdings ALTER COLUMN expected_profit_pct SET DEFAULT 30, DROP COLUMN signal_id,
  DROP COLUMN highest_close, DROP COLUMN trailing_active, DROP COLUMN stop_now,
  DROP COLUMN sell_reason, DROP COLUMN sell_session, DROP COLUMN sell_price, DROP COLUMN tracked_session;
DROP TABLE stock_signal_events;
DROP TABLE stock_signals;
ALTER TABLE stock_screen_results DROP COLUMN momentum, DROP COLUMN watching, DROP COLUMN indicators;
UPDATE rule_definitions SET current_version = 1
WHERE key IN ('stocks.sales_target', 'stocks.alert_new_confirmed',
              'stocks.alert_target_reached', 'stocks.alert_time_elapsed');
DELETE FROM rule_versions
WHERE key IN ('stocks.sales_target', 'stocks.alert_new_confirmed',
              'stocks.alert_target_reached', 'stocks.alert_time_elapsed')
  AND version = 2;
DELETE FROM rule_definitions WHERE key IN (
  'stocks.momentum', 'stocks.watch', 'stocks.ind_candle', 'stocks.ind_macd', 'stocks.ind_pivot',
  'stocks.ind_rsi', 'stocks.ind_stoch', 'stocks.buy_vote', 'stocks.projection', 'stocks.stop_loss',
  'stocks.trailing_stop', 'stocks.sell_vote', 'stocks.alert_watch', 'stocks.alert_projection',
  'stocks.alert_horizon');
UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();
