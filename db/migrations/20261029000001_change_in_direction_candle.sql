-- migrate:up

-- Owners' instructions of 2026-10-29 (spec 08 Stage 4):
-- 1. The price vote is the change in direction candle: the close is higher than the previous
--    session's high. It replaces the TA-Lib bullish patterns; the sell side mirrors it (the
--    close lower than the previous session's low, provisional). It counts at any price.
-- 2. A buy no longer needs the close inside the pullback zone: a qualified stock is already
--    in its pullback. The zone stays part of the qualifying check.
-- 3. A qualifying date keeps the stock on the watch list for 60 sessions (about 3 months).
-- Each rule gets a new version on top of its current one.

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT v.key, v.version + 1, 'provisional', v.enabled, v.counts_toward_minimum,
       'Buy: the change in direction candle, a close higher than the previous session''s high. Sell: a close lower than the previous session''s low (provisional mirror). Counts at any price.',
       '{}', '{}',
       'Owners 2026-10-29: the change in direction candle replaces the candle patterns'
FROM rule_versions v
JOIN rule_definitions d ON d.key = v.key AND d.current_version = v.version
WHERE v.key = 'stocks.ind_candle';

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT v.key, v.version + 1, v.status, v.enabled, v.counts_toward_minimum,
       'A watched stock is bought when at least min_votes different buy indicators fired within the last window_sessions sessions, at any distance from its 52-week high.',
       v.params_schema, v.params,
       'Owners 2026-10-29: no pullback zone check on the buy; a qualified stock is already in its pullback'
FROM rule_versions v
JOIN rule_definitions d ON d.key = v.key AND d.current_version = v.version
WHERE v.key = 'stocks.buy_vote';

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT v.key, v.version + 1, v.status, v.enabled, v.counts_toward_minimum, v.description,
       jsonb_set(v.params_schema, '{watch_sessions,default}', '60'),
       jsonb_set(v.params, '{watch_sessions}', '60'),
       'Owners 2026-10-29: the watch list lasts 60 sessions, about 3 months'
FROM rule_versions v
JOIN rule_definitions d ON d.key = v.key AND d.current_version = v.version
WHERE v.key = 'stocks.watch';

UPDATE rule_definitions SET current_version = current_version + 1,
  source = 'Owners 2026-10-20 and 2026-10-29: a qualifying date stays open 60 sessions (3 months), even below the 10% zone'
WHERE key = 'stocks.watch';

UPDATE rule_definitions d SET current_version = d.current_version + 1,
  name = CASE d.key WHEN 'stocks.ind_candle' THEN 'Change in direction candle' ELSE d.name END,
  source = CASE d.key
    WHEN 'stocks.ind_candle' THEN 'Owners 2026-10-29: the change in direction candle is the close higher than the previous high; sell mirror is a spec 08 interpretation'
    ELSE 'Owners 2026-10-08: 3 of 5 indicators, a window of 3 trading days; 2026-10-29: no pullback zone check'
  END
WHERE d.key IN ('stocks.ind_candle', 'stocks.buy_vote');

UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();

-- migrate:down

UPDATE rule_definitions SET current_version = current_version - 1,
  source = 'Owners 2026-10-20: the qualifying date stays open 40 sessions, even below the 10% zone'
WHERE key = 'stocks.watch';
DELETE FROM rule_versions v USING rule_definitions d
WHERE d.key = v.key AND v.version = d.current_version + 1 AND v.key = 'stocks.watch';

UPDATE rule_definitions d SET current_version = d.current_version - 1,
  name = CASE d.key WHEN 'stocks.ind_candle' THEN 'Price and candle' ELSE d.name END,
  source = CASE d.key
    WHEN 'stocks.ind_candle' THEN 'Owners 2026-10-08: price is the number one indicator, with bullish candles on support'
    ELSE 'Owners 2026-10-08: 3 of 5 indicators, a window of 3 trading days'
  END
WHERE d.key IN ('stocks.ind_candle', 'stocks.buy_vote');
DELETE FROM rule_versions v USING rule_definitions d
WHERE d.key = v.key AND v.version = d.current_version + 1
  AND v.key IN ('stocks.ind_candle', 'stocks.buy_vote');
UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();
