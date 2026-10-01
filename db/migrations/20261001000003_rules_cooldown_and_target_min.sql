-- migrate:up

-- 1. three_eight.cooldown (spec 10): missing from the first seed.
INSERT INTO rule_definitions (key, strategy, kind, name, source, current_version) VALUES
  ('three_eight.cooldown', 'three_eight', 'lifecycle', 'Cooldown',
   'Spec 10 interpretation (dedupe)', 1);

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
VALUES (
  'three_eight.cooldown', 1, 'provisional', true, false,
  'No new 3/8 signal on the same pair and direction within bars of the previous one, even at a different level.',
  '{"bars": {"type": "bars", "default": 4, "min": 0, "max": 96}}',
  '{"bars": 4}',
  'Seeded from the documents'
);

-- 2. three_eight.target version 2: the owners decide in Settings whether the 60-pip
--    minimum rejects closer targets (decision 2026-10-01). Starts as "shown only".
INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT key, 2, status, enabled, counts_toward_minimum,
       description || ' When reject_below_min is on, a target closer than daily_target_min_pips means no trade; when off, the minimum is shown only.',
       params_schema || '{"reject_below_min": {"type": "boolean", "default": false}}'::jsonb,
       params || '{"reject_below_min": false}'::jsonb,
       'Owners choose whether the daily target minimum rejects closer targets'
FROM rule_versions WHERE key = 'three_eight.target' AND version = 1;

UPDATE rule_definitions SET current_version = 2 WHERE key = 'three_eight.target';

UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();

-- migrate:down

UPDATE rule_definitions SET current_version = 1 WHERE key = 'three_eight.target';
DELETE FROM rule_versions WHERE key = 'three_eight.target' AND version = 2;
DELETE FROM rule_definitions WHERE key = 'three_eight.cooldown';
UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();
