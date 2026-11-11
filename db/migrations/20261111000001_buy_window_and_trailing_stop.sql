-- migrate:up

-- Owners 2026-11-11 (spec 08 Stages 4 and 6):
-- 1. Buy window around the qualifying date: from the qualifying date through
--    qualify_after_sessions sessions after it, the buy vote counts the indicators that fired
--    from qualify_before_sessions sessions before the qualifying date. After that the stock
--    stays on the watch list and the usual window_sessions window applies.
-- 2. Trailing stop: starts once the highest close is 5 percent above entry (was 10) and sits
--    10 percent under the highest close (was 5). The stop never falls, so while 10 percent
--    under the highest close is still below the fixed stop, the fixed stop stays.

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT v.key, v.version + 1, 'approved', v.enabled, v.counts_toward_minimum,
       'A watched stock is bought when at least min_votes different buy indicators fired within the last window_sessions sessions, at any distance from its 52-week high. From the qualifying date through qualify_after_sessions sessions after it, the window reaches back to qualify_before_sessions sessions before the qualifying date. With require_volume, a volume spike must be among them and min_votes counts the others.',
       v.params_schema || '{"qualify_before_sessions": {"type": "sessions", "min": 0, "max": 20, "default": 4}, "qualify_after_sessions": {"type": "sessions", "min": 0, "max": 20, "default": 4}}',
       v.params || '{"qualify_before_sessions": 4, "qualify_after_sessions": 4}',
       'Owners 2026-11-11: count buy votes from 4 sessions before to 4 sessions after the qualifying date'
FROM rule_versions v
JOIN rule_definitions d ON d.key = v.key AND d.current_version = v.version
WHERE v.key = 'stocks.buy_vote';

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT v.key, v.version + 1, 'approved', v.enabled, v.counts_toward_minimum,
       'Once the highest close since entry is trail_after_pct above entry, the stop is trail_pct below the highest close and never falls: it stays at the fixed stop until trail_pct below the highest close is higher. A close at or below it is a trailing stop exit.',
       jsonb_set(jsonb_set(v.params_schema, '{trail_pct,default}', '10'), '{trail_after_pct,default}', '5'),
       v.params || '{"trail_pct": 10, "trail_after_pct": 5}',
       'Owners 2026-11-11: start the trailing stop at a 5% gain and trail 10% under the highest close'
FROM rule_versions v
JOIN rule_definitions d ON d.key = v.key AND d.current_version = v.version
WHERE v.key = 'stocks.trailing_stop';

UPDATE rule_definitions SET current_version = current_version + 1
WHERE key IN ('stocks.buy_vote', 'stocks.trailing_stop');
UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();

-- migrate:down

UPDATE rule_definitions SET current_version = current_version - 1
WHERE key IN ('stocks.buy_vote', 'stocks.trailing_stop');
DELETE FROM rule_versions v USING rule_definitions d
WHERE d.key = v.key AND v.version = d.current_version + 1
  AND v.key IN ('stocks.buy_vote', 'stocks.trailing_stop');
UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();
