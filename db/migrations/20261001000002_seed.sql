-- migrate:up

-- Seed data (spec 09 "Seed migration", spec 05 "Seed data").
-- This is the single place where document numbers enter the system.
-- Each parameter's default lives once, in params_schema; params is derived from it.
-- The first admin email is added by db/seed-admin.sh, not here.

-- Instruments (spec 04)

INSERT INTO instruments (symbol, provider_code, asset_class, pip_size, display_decimals, sort_order) VALUES
  ('EUR/USD', 'EUR_USD', 'forex', 0.0001, 5, 1),
  ('GBP/USD', 'GBP_USD', 'forex', 0.0001, 5, 2),
  ('USD/JPY', 'USD_JPY', 'forex', 0.01,   3, 3),
  ('USD/CHF', 'USD_CHF', 'forex', 0.0001, 5, 4),
  ('USD/CAD', 'USD_CAD', 'forex', 0.0001, 5, 5),
  ('AUD/USD', 'AUD_USD', 'forex', 0.0001, 5, 6),
  ('NZD/USD', 'NZD_USD', 'forex', 0.0001, 5, 7);

-- Strategies: all enabled, scanning all enabled instruments

INSERT INTO strategy_configs (strategy, enabled, instrument_ids) VALUES
  ('three_eight', true, NULL),
  ('fib_pivot',   true, NULL),
  ('stocks',      true, NULL);

-- Rules (specs 06, 07, 08), version 1

CREATE TEMP TABLE seed_rules (
  key         text,
  strategy    strategy_key,
  kind        rule_kind,
  name        text,
  source      text,
  status      rule_status,
  counts      boolean,
  description text,
  schema      jsonb
) ON COMMIT DROP;

INSERT INTO seed_rules VALUES

-- 3/8 Formula: context

('three_eight.swing', 'three_eight', 'gate', 'Swings and trend state',
 '3/8 Formula, Trade with the trend; spec 06 context', 'provisional', false,
 'Swing highs and lows come from a ZigZag that reverses after threshold_pips. Trend is up when the last two swing highs and lows are both higher, down when both lower, otherwise none.',
 '{"threshold_pips": {"type": "pips", "default": 20, "min": 5, "max": 100}}'),

-- 3/8 Formula: the eight indicators

('three_eight.candlestick', 'three_eight', 'indicator', 'Candlestick formation',
 '3/8 Formula, Candlestick formations', 'approved', true,
 'A listed pattern completes on the signal bar or the bar before it, in the signal direction. Shaved head or bottom: upper (or lower) shadow at most shaved_max_shadow_pct of the bar range. Doji and spinning top count in the trigger direction.',
 '{"lookback_bars": {"type": "bars", "default": 2, "min": 1, "max": 5},
   "shaved_max_shadow_pct": {"type": "percent", "default": 5, "min": 0, "max": 50},
   "patterns": {"type": "list", "default": ["CDLDOJI", "CDLHAMMER", "CDLINVERTEDHAMMER", "CDLHARAMICROSS", "CDLHANGINGMAN", "CDLDARKCLOUDCOVER", "CDLPIERCING", "CDLSPINNINGTOP", "CDLENGULFING", "SHAVED"],
                "options": ["CDLDOJI", "CDLHAMMER", "CDLINVERTEDHAMMER", "CDLHARAMICROSS", "CDLHANGINGMAN", "CDLDARKCLOUDCOVER", "CDLPIERCING", "CDLSPINNINGTOP", "CDLENGULFING", "SHAVED"]}}'),

('three_eight.hl_failure', 'three_eight', 'indicator', 'New high/low failure',
 '3/8 Formula, New high/low failure', 'approved', true,
 'Price tests the high of the most recent up leg (for shorts) or the low of the most recent down leg (for longs) within test_tolerance_pips and the bar closes without exceeding it.',
 '{"test_tolerance_pips": {"type": "pips", "default": 5, "min": 0, "max": 30}}'),

('three_eight.pivot_touch', 'three_eight', 'indicator', 'Pivots',
 '3/8 Formula, Pivots', 'approved', true,
 'Price trades within the tolerance of a pivot level: daily 10 pips, weekly 15, monthly 15. Daily and weekly (or monthly) levels within double_pivot_pips of each other are marked double pivot.',
 '{"daily_tolerance_pips": {"type": "pips", "default": 10, "min": 1, "max": 50},
   "weekly_tolerance_pips": {"type": "pips", "default": 15, "min": 1, "max": 50},
   "monthly_tolerance_pips": {"type": "pips", "default": 15, "min": 1, "max": 50},
   "double_pivot_pips": {"type": "pips", "default": 10, "min": 0, "max": 50}}'),

('three_eight.flag_pennant_triangle', 'three_eight', 'indicator', 'Flags, pennants, triangles',
 '3/8 Formula, Flags, pennants, triangles; spec 06 interpretation', 'provisional', true,
 'Pole: a move of at least pole_min_pips within pole_max_bars. Consolidation: cons_min_bars to cons_max_bars bars fitting converging or parallel lines. Fires on a close beyond the consolidation in the pattern direction. Projected target: pole length from the breakout.',
 '{"pole_min_pips": {"type": "pips", "default": 30, "min": 5, "max": 200},
   "pole_max_bars": {"type": "bars", "default": 6, "min": 1, "max": 40},
   "cons_min_bars": {"type": "bars", "default": 4, "min": 2, "max": 40},
   "cons_max_bars": {"type": "bars", "default": 20, "min": 2, "max": 100}}'),

('three_eight.trendline_channel', 'three_eight', 'indicator', 'Trendlines and channels',
 '3/8 Formula, Trendlines and channels; spec 06 interpretation', 'provisional', true,
 'A trendline joins swing highs (or lows) with at least min_touches touches within touch_tolerance_pips. Fires when price touches a valid line in the signal direction. A line is invalid after a close beyond it by more than the tolerance. A channel needs a parallel line within parallel_tolerance_pct.',
 '{"min_touches": {"type": "integer", "default": 3, "min": 2, "max": 10},
   "touch_tolerance_pips": {"type": "pips", "default": 3, "min": 0, "max": 20},
   "parallel_tolerance_pct": {"type": "percent", "default": 15, "min": 0, "max": 100},
   "max_line_age_bars": {"type": "bars", "default": 480, "min": 10, "max": 5000}}'),

('three_eight.pdh', 'three_eight', 'indicator', 'Previous day''s high',
 '3/8 Formula, Previous day''s high', 'approved', true,
 'Price trades within tolerance_pips of the previous New York day high. Supports shorts at a rejection and longs on a confirmed break and retest.',
 '{"tolerance_pips": {"type": "pips", "default": 10, "min": 1, "max": 50}}'),

('three_eight.pdl', 'three_eight', 'indicator', 'Previous day''s low',
 '3/8 Formula, Previous day''s low', 'approved', true,
 'Price trades within tolerance_pips of the previous New York day low. Mirror of the previous day high rule.',
 '{"tolerance_pips": {"type": "pips", "default": 10, "min": 1, "max": 50}}'),

('three_eight.fibonacci', 'three_eight', 'indicator', 'Fibonacci',
 '3/8 Formula, Fibonacci', 'approved', true,
 'Price trades within tolerance_pips of a retracement of the last leg. ratio_set fib uses 0.382, 0.5, 0.618; thirds uses 1/3, 1/2, 2/3.',
 '{"tolerance_pips": {"type": "pips", "default": 5, "min": 0, "max": 30},
   "ratio_set": {"type": "enum", "default": "fib", "options": ["fib", "thirds"]}}'),

-- 3/8 Formula: supplementary indicators (shown, not counted by default)

('three_eight.thrust_candle', 'three_eight', 'indicator', 'Thrust candle',
 '3/8 Formula, Thrust candle (counts "sometimes")', 'provisional', false,
 'A bar whose body is at least min_body_pips. Shown as supporting evidence; admins can switch on counting toward the minimum.',
 '{"min_body_pips": {"type": "pips", "default": 15, "min": 1, "max": 100}}'),

('three_eight.hook_reversal', 'three_eight', 'indicator', 'Hook reversal / blended hook',
 '3/8 Formula, Hook reversal (counts "sometimes")', 'provisional', false,
 'After a leg of at least min_leg_pips, two consecutive bars form a reversal hook: the second bar opens beyond and closes back inside the first bar range.',
 '{"min_leg_pips": {"type": "pips", "default": 60, "min": 5, "max": 300}}'),

-- 3/8 Formula: trigger and gates

('three_eight.trigger', 'three_eight', 'gate', 'Trigger location',
 '3/8 Formula, Trades triggered off pivots; only exception FIBS', 'approved', false,
 'A candidate exists only when the pivot or Fibonacci indicator fires on the bar. Long when the level is at or below the bar close, short when at or above.',
 '{}'),

('three_eight.min_indicators', 'three_eight', 'gate', 'Minimum indicators',
 '3/8 Formula, 3 of 8', 'approved', false,
 'The count of fired counting indicators in the candidate direction must be at least minimum. The trigger indicator counts.',
 '{"minimum": {"type": "integer", "default": 3, "min": 1, "max": 8}}'),

('three_eight.trading_window', 'three_eight', 'gate', 'Trading hours',
 '3/8 Formula, Trading hours', 'approved', false,
 'Bar close time must fall inside the active window. Primary 00:00 to 10:30, alternative 05:00 to 14:00, in the configured time zone.',
 '{"window": {"type": "enum", "default": "primary", "options": ["primary", "alternative", "both"]},
   "primary_start": {"type": "time", "default": "00:00"},
   "primary_end": {"type": "time", "default": "10:30"},
   "alternative_start": {"type": "time", "default": "05:00"},
   "alternative_end": {"type": "time", "default": "14:00"},
   "timezone": {"type": "enum", "default": "America/New_York", "options": ["America/New_York"]}}'),

('three_eight.trend_alignment', 'three_eight', 'gate', 'Trade with the trend',
 '3/8 Formula, Trade with the trend', 'approved', false,
 'Direction must match the trend state. With no trend, candidates are allowed only in range mode.',
 '{}'),

('three_eight.countertrend', 'three_eight', 'gate', 'Countertrend exception',
 '3/8 Formula, Countertrend trades', 'approved', false,
 'A countertrend candidate needs a move of at least min_move_pips in the trend direction since the last opposite swing, not made within fast_move_bars bars (a fast_move_pips move that fast blocks it). After a consolidation of new_trend_consolidation_hours that resolves the other way, the move is a new trend.',
 '{"min_move_pips": {"type": "pips", "default": 50, "min": 5, "max": 300},
   "fast_move_pips": {"type": "pips", "default": 50, "min": 5, "max": 300},
   "fast_move_bars": {"type": "bars", "default": 4, "min": 1, "max": 20},
   "new_trend_consolidation_hours": {"type": "hours", "default": 8, "min": 1, "max": 48}}'),

('three_eight.econ', 'three_eight', 'gate', 'Econ reports',
 '3/8 Formula, Econ reports; large bar size is spec 06 interpretation', 'approved', false,
 'Within window_minutes after a logged high-impact event for either currency: countertrend only off a single 15-minute bar of at least large_bar_pips; a large move followed by a reversing candle is always allowed regardless of stop distance; Fibonacci levels may not be targets.',
 '{"window_minutes": {"type": "minutes", "default": 60, "min": 5, "max": 240},
   "large_bar_pips": {"type": "pips", "default": 25, "min": 5, "max": 200}}'),

('three_eight.stop_feasible', 'three_eight', 'gate', 'Stop placement possible',
 '3/8 Formula, Stop placement', 'approved', false,
 'The planner must find a valid stop. If not, no trade.',
 '{}'),

('three_eight.reward_risk', 'three_eight', 'gate', 'Target greater than risk',
 '3/8 Formula, Target greater than risk (example 25/20)', 'approved', false,
 'Target distance divided by stop distance must be at least min_ratio.',
 '{"min_ratio": {"type": "ratio", "default": 1.25, "min": 0.5, "max": 10}}'),

('three_eight.daily_goal', 'three_eight', 'gate', 'Daily target',
 '3/8 Formula, Daily target 60 to 75 pips; suppression is spec 06 interpretation', 'provisional', false,
 'Daily goal of goal_min_pips to goal_max_pips from closed signal outcomes. When suppress_after_goal is on, new 3/8 alerts on a pair stop once the goal is reached that day.',
 '{"goal_min_pips": {"type": "pips", "default": 60, "min": 0, "max": 500},
   "goal_max_pips": {"type": "pips", "default": 75, "min": 0, "max": 500},
   "suppress_after_goal": {"type": "boolean", "default": false}}'),

-- 3/8 Formula: planner

('three_eight.entry', 'three_eight', 'plan', 'Entry',
 'Spec 06 interpretation', 'provisional', false,
 'Entry is the close of the signal bar (reference mid price). Broker adjustment is applied later.',
 '{}'),

('three_eight.stop', 'three_eight', 'plan', 'Stop',
 '3/8 Formula, Stop placement', 'approved', false,
 'At a pivot trigger: stop beyond the nearest pivot on the far side of entry, at pivot_stop_min_pips to pivot_stop_max_pips. Otherwise buffer_pips beyond the previous swing, using the smallest distance within fallback_min_pips to fallback_max_pips that clears it.',
 '{"pivot_stop_min_pips": {"type": "pips", "default": 20, "min": 1, "max": 200},
   "pivot_stop_max_pips": {"type": "pips", "default": 25, "min": 1, "max": 200},
   "buffer_pips": {"type": "pips", "default": 1, "min": 0, "max": 20},
   "fallback_min_pips": {"type": "pips", "default": 20, "min": 1, "max": 200},
   "fallback_max_pips": {"type": "pips", "default": 25, "min": 1, "max": 200}}'),

('three_eight.target', 'three_eight', 'plan', 'Target',
 '3/8 Formula, Target is always furthest pivot unless resistance; spec 06 interpretation', 'provisional', false,
 'Furthest pivot in the trade direction within daily_target_max_pips, capped at the previous day high (longs) or low (shorts) when that lies between. Countertrend: nearest Fibonacci level, then nearest pivot, capped at countertrend_target_max_pips. Pattern targets shown as an alternative.',
 '{"daily_target_min_pips": {"type": "pips", "default": 60, "min": 1, "max": 500},
   "daily_target_max_pips": {"type": "pips", "default": 75, "min": 1, "max": 500},
   "countertrend_target_min_pips": {"type": "pips", "default": 20, "min": 1, "max": 200},
   "countertrend_target_max_pips": {"type": "pips", "default": 25, "min": 1, "max": 200}}'),

-- 3/8 Formula: range mode and expiry

('three_eight.range_detect', 'three_eight', 'gate', 'Range detection',
 '3/8 Formula, Transitioning market; thresholds are spec 06 interpretation', 'provisional', false,
 'Ranging when, over the last lookback_bars, price retested the same high or low at least min_retests times within retest_tolerance_pips, and the range is at least min_width_pips wide.',
 '{"lookback_bars": {"type": "bars", "default": 32, "min": 4, "max": 200},
   "min_retests": {"type": "integer", "default": 2, "min": 1, "max": 10},
   "retest_tolerance_pips": {"type": "pips", "default": 5, "min": 0, "max": 30},
   "min_width_pips": {"type": "pips", "default": 20, "min": 1, "max": 300}}'),

('three_eight.range_mode', 'three_eight', 'gate', 'Range mode',
 '3/8 Formula, Show more flexibility; settings are spec 06 interpretation', 'provisional', false,
 'In range mode: candidates inside the range, long near the low, short near the high; Fibonacci and countertrend allowed; minimum count is range_minimum; targets cap at the opposite side of the range.',
 '{"range_minimum": {"type": "integer", "default": 3, "min": 1, "max": 8}}'),

('three_eight.expiry', 'three_eight', 'lifecycle', 'Signal expiry',
 'Spec 06 interpretation', 'provisional', false,
 'An open signal expires at the end of the trading window or after max_bars bars, whichever comes first.',
 '{"max_bars": {"type": "bars", "default": 16, "min": 1, "max": 200}}'),

-- Fibonacci Pivot (spec 07)

('fib_pivot.unit', 'fib_pivot', 'plan', 'Unit',
 'Fibonacci Pivot Point notes (example in dollars and cents); spec 07 interpretation', 'provisional', false,
 'Unit used to convert the range to a Fibonacci number. Forex uses pips.',
 '{"forex_unit": {"type": "enum", "default": "pip", "options": ["pip"]}}'),

('fib_pivot.levels', 'fib_pivot', 'plan', 'Level calculation',
 'Fibonacci Pivot Point notes', 'approved', false,
 'Range in units = prior day high minus low. Take the closest Fibonacci number (ties go to the larger), clamped to min_fib and max_fib, and the next three as offsets. Pivot = prior day close. Break, Confirmation, Take Profit, Reset at Pivot plus and minus each offset.',
 '{"min_fib": {"type": "integer", "default": 13, "min": 1, "max": 987},
   "max_fib": {"type": "integer", "default": 987, "min": 1, "max": 987}}'),

('fib_pivot.entry', 'fib_pivot', 'plan', 'Entry',
 'Spec 07 interpretation (notes give no entry)', 'provisional', false,
 'Long when a completed 15-minute bar closes above the upper Break, short on a close below the lower Break. Entry is that bar close.',
 '{"trigger": {"type": "enum", "default": "close_beyond", "options": ["close_beyond", "touch"]}}'),

('fib_pivot.confirmation', 'fib_pivot', 'lifecycle', 'Confirmation',
 'Spec 07 interpretation', 'provisional', false,
 'When price reaches the Confirmation level in the trade direction, the signal is marked confirmed and an update is sent.',
 '{"notify_on_confirm": {"type": "boolean", "default": true}}'),

('fib_pivot.stop', 'fib_pivot', 'plan', 'Stop',
 'Spec 07 interpretation (notes give no stop)', 'provisional', false,
 'Stop at the Pivot (prior close), or at the opposite Break.',
 '{"stop_at": {"type": "enum", "default": "pivot", "options": ["pivot", "opposite_break"]}}'),

('fib_pivot.target', 'fib_pivot', 'plan', 'Target',
 'Spec 07 interpretation (notes give no target)', 'provisional', false,
 'Target at the chosen level.',
 '{"target_at": {"type": "enum", "default": "take_profit", "options": ["confirmation", "take_profit", "reset"]}}'),

('fib_pivot.reset', 'fib_pivot', 'lifecycle', 'Reset reached',
 'Spec 07 interpretation', 'provisional', false,
 'If price reaches Reset, the signal is marked extended and an update is sent.',
 '{"notify_on_reset": {"type": "boolean", "default": true}}'),

('fib_pivot.one_per_side', 'fib_pivot', 'lifecycle', 'One signal per side per day',
 'Spec 07 interpretation', 'provisional', false,
 'At most max_per_side_per_day long and short signals per pair per day.',
 '{"max_per_side_per_day": {"type": "integer", "default": 1, "min": 1, "max": 10}}'),

('fib_pivot.window', 'fib_pivot', 'gate', 'Trading window',
 'Spec 07 interpretation', 'provisional', false,
 'Triggers are checked during the 3/8 trading window so the two systems share a schedule.',
 '{"window": {"type": "enum", "default": "primary", "options": ["primary", "alternative", "both"]}}'),

('fib_pivot.expiry', 'fib_pivot', 'lifecycle', 'Expiry',
 'Spec 07 interpretation', 'provisional', false,
 'Open signals expire at the 17:00 New York roll.',
 '{"expire_at_day_roll": {"type": "boolean", "default": true}}'),

('fib_pivot.confluence', 'fib_pivot', 'lifecycle', 'Confluence marker',
 'Spec 07 interpretation', 'provisional', false,
 'When a 3/8 signal and a Fibonacci Pivot signal agree in direction on the same pair within confluence_bars, both show a confluence marker. Does not change either signal.',
 '{"confluence_bars": {"type": "bars", "default": 4, "min": 0, "max": 96}}'),

-- Stock screener (spec 08)

('stocks.universe', 'stocks', 'filter', 'Universe',
 'Financial Wealth Building, comb through the entire NYSE and the Nasdaq', 'approved', false,
 'Active common stocks on NYSE, Nasdaq, and NYSE American. OTC excluded.',
 '{"exchanges": {"type": "list", "default": ["XNYS", "XNAS", "XASE"], "options": ["XNYS", "XNAS", "XASE"]}}'),

('stocks.liquidity', 'stocks', 'filter', 'Liquidity',
 'Spec 08 interpretation (documents set no filter)', 'provisional', false,
 'Exclude stocks below min_price or with average volume over avg_volume_sessions below min_avg_volume. Set both to 0 to switch off.',
 '{"min_price": {"type": "price", "default": 1.00, "min": 0, "max": 1000},
   "min_avg_volume": {"type": "integer", "default": 100000, "min": 0, "max": 100000000},
   "avg_volume_sessions": {"type": "sessions", "default": 20, "min": 1, "max": 252}}'),

('stocks.history_required', 'stocks', 'filter', 'History required',
 'Financial Wealth Building, 52-week figures', 'approved', false,
 'A stock needs at least min_sessions of history. 52-week high and low use the highest high and lowest low over lookback_sessions.',
 '{"min_sessions": {"type": "sessions", "default": 252, "min": 51, "max": 400},
   "lookback_sessions": {"type": "sessions", "default": 252, "min": 51, "max": 400}}'),

('stocks.rule1_near_high', 'stocks', 'filter', 'Close near the 52-week high',
 'Financial Wealth Building 1, Rule 1', 'approved', false,
 'Last close at least the 52-week high times ratio.',
 '{"ratio": {"type": "ratio", "default": 0.90, "min": 0, "max": 1}}'),

('stocks.rule2_double', 'stocks', 'filter', 'High at least twice the low',
 'Financial Wealth Building 1, Rule 2', 'approved', false,
 '52-week high at least the 52-week low times multiple.',
 '{"multiple": {"type": "ratio", "default": 2.0, "min": 1, "max": 20}}'),

('stocks.rule3_apr', 'stocks', 'filter', 'Annual percentage rate',
 'Financial Wealth Building 1, Rule 3', 'approved', false,
 'APR = (52-week high minus 52-week low) / 52-week low, at least min_apr.',
 '{"min_apr": {"type": "ratio", "default": 1.00, "min": 0, "max": 20}}'),

('stocks.five_line', 'stocks', 'plan', 'Five line chart',
 'Financial Wealth Building 1, five line chart', 'approved', false,
 'For N in periods: ACC_N = (C0 minus CN) / CN; APR_N = ACC_N / N times trader_year.',
 '{"trader_year": {"type": "integer", "default": 260, "min": 200, "max": 366},
   "periods": {"type": "list", "default": [5, 10, 20, 50], "options": [5, 10, 20, 50]}}'),

('stocks.trend_established', 'stocks', 'gate', 'Trend established',
 'Financial Wealth Building, Steps 3 to 5', 'approved', false,
 'The 20-day establishes a trend: ACC_20 greater than min_acc.',
 '{"min_acc": {"type": "ratio", "default": 0, "min": -1, "max": 10}}'),

('stocks.trend_confirmed', 'stocks', 'gate', 'Trend confirmed',
 'Financial Wealth Building, Steps 3 to 5', 'approved', false,
 'The 50-day confirms the trend: ACC_50 greater than min_acc while the 20-day condition holds.',
 '{"min_acc": {"type": "ratio", "default": 0, "min": -1, "max": 10}}'),

('stocks.trend_consistent', 'stocks', 'indicator', 'Consistent movement',
 'Financial Wealth Building, Steps 3 to 5; spec 08 interpretation', 'provisional', false,
 'ACC_5 and ACC_10 both greater than min_acc. Shown as a flag; required for an alert only when required_for_alert is on.',
 '{"min_acc": {"type": "ratio", "default": 0, "min": -1, "max": 10},
   "required_for_alert": {"type": "boolean", "default": false}}'),

('stocks.sales_target', 'stocks', 'plan', 'Sales target',
 'Entry Points and Sales Targets', 'approved', false,
 'Sales target = purchase price times (1 + expected profit). Daily target = earnings / horizon_sessions; weekly = daily times 5. Defaults for new holdings.',
 '{"expected_profit_pct": {"type": "percent", "default": 30, "min": 1, "max": 1000},
   "horizon_sessions": {"type": "sessions", "default": 20, "min": 1, "max": 260}}'),

('stocks.alert_new_confirmed', 'stocks', 'lifecycle', 'Newly confirmed digest',
 'Spec 08 interpretation (alert timing not stated)', 'provisional', false,
 'One evening digest lists stocks that reached trend confirmed today and were not confirmed in the prior cooldown_sessions, up to max_in_digest.',
 '{"cooldown_sessions": {"type": "sessions", "default": 10, "min": 0, "max": 260},
   "max_in_digest": {"type": "integer", "default": 25, "min": 1, "max": 500}}'),

('stocks.alert_target_reached', 'stocks', 'lifecycle', 'Sales target reached',
 'Entry Points and Sales Targets', 'approved', false,
 'Alert when a holding closes at or above its sales target.',
 '{}'),

('stocks.alert_time_elapsed', 'stocks', 'lifecycle', 'Time elapsed',
 'Spec 08 interpretation', 'provisional', false,
 'Alert when a holding reaches horizon_sessions without hitting its target.',
 '{"horizon_sessions": {"type": "sessions", "default": 20, "min": 1, "max": 260}}');

INSERT INTO rule_definitions (key, strategy, kind, name, source, current_version)
SELECT key, strategy, kind, name, source, 1 FROM seed_rules;

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT key, 1, status, true, counts, description, schema,
       COALESCE((SELECT jsonb_object_agg(p.key, p.value -> 'default')
                 FROM jsonb_each(schema) AS p), '{}'::jsonb),
       'Seeded from the documents'
FROM seed_rules;

DROP TABLE seed_rules;

-- Singletons

INSERT INTO rule_config_revision (id, revision) VALUES (true, 1);
INSERT INTO worker_heartbeat (id, at, version) VALUES (true, now(), 'seed');

-- migrate:down

DELETE FROM worker_heartbeat;
DELETE FROM rule_config_revision;
DELETE FROM rule_versions WHERE version = 1 AND change_note = 'Seeded from the documents';
DELETE FROM rule_definitions WHERE NOT EXISTS (
  SELECT 1 FROM rule_versions v WHERE v.key = rule_definitions.key);
DELETE FROM strategy_configs;
DELETE FROM instruments WHERE symbol IN
  ('EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'USD/CAD', 'AUD/USD', 'NZD/USD');
