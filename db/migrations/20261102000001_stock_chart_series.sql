-- migrate:up

-- The indicator lines the stock page draws under the candles (spec 13), written by the
-- scanner from the same code as the votes. One row per stock: the latest screen replaces it.
CREATE TABLE stock_chart_series (
  ticker       text PRIMARY KEY,
  session_date date NOT NULL,        -- the last session the lines run to
  series       jsonb NOT NULL,
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- migrate:down

DROP TABLE stock_chart_series;
