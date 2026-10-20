-- migrate:up

-- The 10-week momentum filter (spec 08, owners' instructions of 2026-10-20). The momentum test
-- moves from the 10-day APR on every session to a ladder on the week's close: from the Friday
-- close (Thursday when Friday is closed), the rate from each of the last 10 weekly closes, with
-- at least 5 of the 10 at the threshold. A pass keeps the stock watched for 40 sessions.
-- Each rule gets a new version on top of its current one, keeping the owners' projection,
-- horizon, and trend setting.

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT v.key, v.version + 1, 'approved', v.enabled, v.counts_toward_minimum,
       'On the week''s close (the Friday, or the session before a closed Friday) that passes the qualifying rules: for each of 1 to weeks weeks back, (close - that week''s close) / that week''s close / (weeks back x days_per_week) x the trader year. Passes when at least min_weeks_passing of them reach projection_pct / 100 / horizon_sessions x the trader year (0.35 / 20 x 260 = 455 percent).',
       '{"weeks": {"type": "integer", "default": 10, "min": 1, "max": 52},
         "min_weeks_passing": {"type": "integer", "default": 5, "min": 1, "max": 52},
         "days_per_week": {"type": "integer", "default": 5, "min": 1, "max": 7},
         "projection_pct": {"type": "percent", "default": 35, "min": 1, "max": 1000},
         "horizon_sessions": {"type": "sessions", "default": 20, "min": 1, "max": 260}}',
       jsonb_build_object('weeks', 10, 'min_weeks_passing', 5, 'days_per_week', 5,
                          'projection_pct', v.params -> 'projection_pct',
                          'horizon_sessions', v.params -> 'horizon_sessions'),
       'Owners 2026-10-20: 10 weeks back from the Friday close, at least 5 of 10 at 455 percent'
FROM rule_versions v
JOIN rule_definitions d ON d.key = v.key AND d.current_version = v.version
WHERE v.key = 'stocks.momentum';

INSERT INTO rule_versions (key, version, status, enabled, counts_toward_minimum,
                           description, params_schema, params, change_note)
SELECT v.key, v.version + 1, v.status, v.enabled, v.counts_toward_minimum,
       'A qualified stock that passes the momentum test on the week''s close (its qualifying date) joins the watch list. It stays while it is still qualified, for up to watch_sessions after it last passed, and leaves when bought.',
       '{"watch_sessions": {"type": "sessions", "default": 40, "min": 1, "max": 260},
         "require_trend_confirmed": {"type": "boolean", "default": false}}',
       jsonb_build_object('watch_sessions', 40,
                          'require_trend_confirmed', v.params -> 'require_trend_confirmed'),
       'Owners 2026-10-20: a qualifying date stays open for 40 sessions'
FROM rule_versions v
JOIN rule_definitions d ON d.key = v.key AND d.current_version = v.version
WHERE v.key = 'stocks.watch';

UPDATE rule_definitions d SET current_version = d.current_version + 1,
  name = CASE d.key WHEN 'stocks.momentum' THEN '10-week momentum' ELSE d.name END,
  source = CASE d.key
    WHEN 'stocks.momentum' THEN 'Owners 2026-10-20: the Friday close, 10 weeks back, 455% on at least 5 of 10'
    ELSE 'Owners 2026-10-20: the qualifying date stays open 40 sessions; leaving below the zone is a spec 08 interpretation'
  END
WHERE d.key IN ('stocks.momentum', 'stocks.watch');

UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();

-- migrate:down

UPDATE rule_definitions d SET current_version = d.current_version - 1,
  name = CASE d.key WHEN 'stocks.momentum' THEN 'Momentum' ELSE 'Watch list' END,
  source = CASE d.key
    WHEN 'stocks.momentum' THEN 'Owners 2026-10-08: 455% with the 10 day, so 35% in 20 days; 5 Line Bar'
    ELSE 'Owners 2026-10-08: catch the support within the 10% pullback; spec 08 interpretation'
  END
WHERE d.key IN ('stocks.momentum', 'stocks.watch');
DELETE FROM rule_versions v USING rule_definitions d
WHERE d.key = v.key AND v.version = d.current_version + 1
  AND v.key IN ('stocks.momentum', 'stocks.watch');
UPDATE rule_config_revision SET revision = revision + 1, updated_at = now();
