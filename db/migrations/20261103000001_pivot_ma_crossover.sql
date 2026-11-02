-- migrate:up

-- The client's pivot point moving average double crossover replaces the floor trader pivot
-- as the pivot vote (owners 2026-11-02, spec 08 Stage 4): the 10-session average of each
-- session's pivot (high + low + close) / 3, crossing its own 3-session average.

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT v.key, v.version + 1, 'approved', v.enabled, v.counts_toward_minimum,
       'Each session''s pivot is (high + low + close) / 3. The pivot MA is its ma_sessions simple average; the signal line is the signal_sessions average of the pivot MA. Buy: the pivot MA crosses above the signal line. Sell: it crosses below.',
       '{"ma_sessions": {"type": "sessions", "default": 10, "min": 2, "max": 100},
         "signal_sessions": {"type": "sessions", "default": 3, "min": 1, "max": 50}}',
       '{"ma_sessions": 10, "signal_sessions": 3}',
       'Owners 2026-11-02: the client''s pivot point moving average double crossover'
FROM rule_versions v
JOIN rule_definitions d ON d.key = v.key AND d.current_version = v.version
WHERE v.key = 'stocks.ind_pivot';

UPDATE rule_definitions SET current_version = current_version + 1,
  name = 'Pivot point MA crossover',
  source = 'Owners 2026-11-02: the client''s pivot point moving average double crossover'
WHERE key = 'stocks.ind_pivot';

UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();

-- migrate:down

UPDATE rule_definitions SET current_version = current_version - 1,
  name = 'Pivot point crossover',
  source = 'Owners 2026-10-29: the standard floor trader pivot'
WHERE key = 'stocks.ind_pivot';
DELETE FROM rule_versions v USING rule_definitions d
WHERE d.key = v.key AND v.version = d.current_version + 1 AND v.key = 'stocks.ind_pivot';
UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();
