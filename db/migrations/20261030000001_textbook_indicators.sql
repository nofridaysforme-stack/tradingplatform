-- migrate:up

-- The owners' instructions of 2026-10-29: the indicators follow their standard (textbook)
-- rules, and two are added (spec 08 Stage 4).
-- Stochastics: George Lane, %K crossing %D while both are below 20 (buy) or above 80 (sell).
-- Pivot point: the floor trader pivot of the session before; the close crossing it.
-- Moving average crossover (new): the 10-session average crossing the 20-session average.
-- Volume spike (new): volume at least 1.5 times its 20-session average, on an up or down close.
-- Buy vote: a volume spike must confirm the buy; 3 of the other 6 indicators.
-- Each changed rule gets a new version on top of its current one.

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT v.key, v.version + 1, 'approved', v.enabled, v.counts_toward_minimum,
       'George Lane''s slow stochastic. Buy: %K crosses above %D while both are below buy_level. Sell: %K crosses below %D while both are above sell_level.',
       v.params_schema, v.params,
       'Owners 2026-10-29: the standard rule (Lane) replaces %K crossing the level'
FROM rule_versions v
JOIN rule_definitions d ON d.key = v.key AND d.current_version = v.version
WHERE v.key = 'stocks.ind_stoch';

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT v.key, v.version + 1, 'approved', v.enabled, v.counts_toward_minimum,
       'The floor trader pivot: (high + low + close) / 3 of the session before. Buy: the close crosses above the pivot. Sell: the close crosses below it.',
       '{}', '{}',
       'Owners 2026-10-29: the standard pivot rule replaces the pivot line over its 3-day average'
FROM rule_versions v
JOIN rule_definitions d ON d.key = v.key AND d.current_version = v.version
WHERE v.key = 'stocks.ind_pivot';

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT v.key, v.version + 1, 'provisional', v.enabled, v.counts_toward_minimum,
       'A watched stock is bought when a volume spike (if require_volume) and at least min_votes different other buy indicators fired within the last window_sessions sessions, at any distance from its 52-week high.',
       v.params_schema || '{"require_volume": {"type": "boolean", "default": true}}',
       v.params || '{"require_volume": true}',
       'Owners 2026-10-29: volume confirms the buy'
FROM rule_versions v
JOIN rule_definitions d ON d.key = v.key AND d.current_version = v.version
WHERE v.key = 'stocks.buy_vote';

UPDATE rule_definitions SET current_version = current_version + 1
WHERE key IN ('stocks.ind_stoch', 'stocks.ind_pivot', 'stocks.buy_vote');
UPDATE rule_definitions SET
  source = 'Owners 2026-10-29: the standard rules (George Lane)'
WHERE key = 'stocks.ind_stoch';
UPDATE rule_definitions SET
  source = 'Owners 2026-10-29: the standard floor trader pivot'
WHERE key = 'stocks.ind_pivot';
UPDATE rule_definitions SET
  source = 'Owners 2026-10-08: 3 of 5 indicators, a window of 3 trading days; 2026-10-29: no pullback zone check, volume confirms'
WHERE key = 'stocks.buy_vote';

INSERT INTO rule_definitions (key, strategy, kind, name, source, current_version) VALUES
('stocks.ind_ma', 'stocks', 'indicator', 'Moving average crossover',
 'Owners 2026-10-29: moving average crossover; the 10 and 20 session lengths are a spec 08 suggestion', 1),
('stocks.ind_volume', 'stocks', 'indicator', 'Volume spike',
 'Owners 2026-10-29: volume spike; 1.5 times the 20-session average is a spec 08 suggestion', 1);

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note) VALUES
('stocks.ind_ma', 1, 'provisional', true, true,
 'Simple moving averages of the close. Buy: the short_sessions average crosses above the long_sessions average. Sell: it crosses below.',
 '{"short_sessions": {"type": "sessions", "default": 10, "min": 2, "max": 200},
   "long_sessions": {"type": "sessions", "default": 20, "min": 3, "max": 400}}',
 '{"short_sessions": 10, "long_sessions": 20}',
 'Seeded from the owners'' instructions of 2026-10-29'),
('stocks.ind_volume', 1, 'provisional', true, true,
 'Volume at least multiple times the average of the average_sessions sessions before. Buy: on a close above the previous close. Sell: on a close below it.',
 '{"average_sessions": {"type": "sessions", "default": 20, "min": 2, "max": 200},
   "multiple": {"type": "ratio", "default": 1.5, "min": 1, "max": 10}}',
 '{"average_sessions": 20, "multiple": 1.5}',
 'Seeded from the owners'' instructions of 2026-10-29');

UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();

-- migrate:down

DELETE FROM rule_definitions WHERE key IN ('stocks.ind_ma', 'stocks.ind_volume');
UPDATE rule_definitions SET current_version = current_version - 1
WHERE key IN ('stocks.ind_stoch', 'stocks.ind_pivot', 'stocks.buy_vote');
UPDATE rule_definitions SET
  source = 'Owners 2026-10-08: Stochastics crossing over the 20; sell level is a spec 08 interpretation'
WHERE key = 'stocks.ind_stoch';
UPDATE rule_definitions SET
  source = 'Owners 2026-10-08: the pivot point as a line, with a 3 day average crossover'
WHERE key = 'stocks.ind_pivot';
UPDATE rule_definitions SET
  source = 'Owners 2026-10-08: 3 of 5 indicators, a window of 3 trading days; 2026-10-29: no pullback zone check'
WHERE key = 'stocks.buy_vote';
DELETE FROM rule_versions v USING rule_definitions d
WHERE d.key = v.key AND v.version = d.current_version + 1
  AND v.key IN ('stocks.ind_stoch', 'stocks.ind_pivot', 'stocks.buy_vote');
UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();
