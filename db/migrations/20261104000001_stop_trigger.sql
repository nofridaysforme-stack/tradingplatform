-- migrate:up

-- A setting for how the fixed and trailing stops are hit (spec 08 Stage 6, open item A34):
-- "close" (the rule so far: a close at or below the stop) or "intraday" (the session's low
-- reaches the stop; the exit is at the stop, or at the open when the session opened below
-- it). The default stays "close"; "intraday" is for the backtest comparison the owners asked
-- for on 2026-11-03 until they decide.

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT v.key, v.version + 1, v.status, v.enabled, v.counts_toward_minimum,
       'Until the trailing stop starts, the trade exits at entry x (1 - stop_pct). With trigger "close" a close at or below the stop exits at that close; with "intraday" the session''s low reaching the stop exits at the stop, or at the open when the session opened below it. The trigger applies to the trailing stop too.',
       v.params_schema || '{"trigger": {"type": "enum", "default": "close", "options": ["close", "intraday"]}}',
       v.params || '{"trigger": "close"}',
       'Owners 2026-11-03: compare stops hit on the close with stops hit during the session'
FROM rule_versions v
JOIN rule_definitions d ON d.key = v.key AND d.current_version = v.version
WHERE v.key = 'stocks.stop_loss';

UPDATE rule_definitions SET current_version = current_version + 1 WHERE key = 'stocks.stop_loss';
UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();

-- migrate:down

UPDATE rule_definitions SET current_version = current_version - 1 WHERE key = 'stocks.stop_loss';
DELETE FROM rule_versions v USING rule_definitions d
WHERE d.key = v.key AND v.version = d.current_version + 1 AND v.key = 'stocks.stop_loss';
UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();
