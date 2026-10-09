-- migrate:up

-- Portal-wide switches, one row. forex_enabled pauses the whole forex side: the scanner stops
-- its forex jobs and the portal hides the forex pages. Nothing is deleted, and turning it back
-- on in Settings resumes everything as it was.
CREATE TABLE app_settings (
  id            boolean PRIMARY KEY DEFAULT true CHECK (id),
  forex_enabled boolean NOT NULL DEFAULT true,
  updated_by    uuid REFERENCES users(id),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

-- Forex is paused at the owners' request (decision 2026-10-08, spec 20).
INSERT INTO app_settings (forex_enabled) VALUES (false);

-- migrate:down

DROP TABLE app_settings;
