-- migrate:up

-- Delivery (spec 11): retries at 5, 20, and 60 seconds, and each event sent once per owner
-- per channel even if the dispatcher runs again.
ALTER TABLE notifications
  ADD COLUMN next_attempt_at timestamptz,
  ADD COLUMN dedupe_key text;
CREATE UNIQUE INDEX notifications_dedupe_idx
  ON notifications (dedupe_key, coalesce(user_id, '00000000-0000-0000-0000-000000000000'::uuid), channel)
  WHERE dedupe_key IS NOT NULL;
CREATE INDEX notifications_due_idx ON notifications (next_attempt_at) WHERE status = 'queued';

-- How far the dispatcher has read signal_events.
CREATE TABLE notify_cursor (
  name        text PRIMARY KEY,
  last_id     bigint NOT NULL DEFAULT 0,
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Health alert state: repeat at most once an hour, then send "Resolved" when it clears.
CREATE TABLE health_alerts (
  condition     text PRIMARY KEY,               -- 'heartbeat_stale', 'pair_stale:EUR/USD', ...
  first_seen_at timestamptz NOT NULL,
  last_sent_at  timestamptz,
  resolved_at   timestamptz,
  detail        jsonb NOT NULL DEFAULT '{}'
);

-- migrate:down

DROP TABLE health_alerts;
DROP TABLE notify_cursor;
DROP INDEX notifications_due_idx;
DROP INDEX notifications_dedupe_idx;
ALTER TABLE notifications DROP COLUMN dedupe_key, DROP COLUMN next_attempt_at;
