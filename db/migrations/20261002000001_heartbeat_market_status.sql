-- migrate:up

-- The worker writes the forex market status with each heartbeat (open or closed, the 3/8
-- trading window, stale pairs) so the portal shows it without repeating rule logic.
ALTER TABLE worker_heartbeat ADD COLUMN market jsonb;

-- migrate:down

ALTER TABLE worker_heartbeat DROP COLUMN market;
