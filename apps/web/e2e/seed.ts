import type postgres from "postgres";

// Signals, levels, candles, and a heartbeat in the shapes the scanner writes, for the
// end-to-end tests and local screenshots. Everything hangs off two test pairs that are not
// in the seeded set (EUR/GBP, GBP/JPY), so clearing them never touches real market data.

export const SIGNAL_38 = "e2e00000-0000-4000-8000-000000000038";
export const SIGNAL_FIB = "e2e00000-0000-4000-8000-0000000000f1";
export const SIGNAL_CLOSED = "e2e00000-0000-4000-8000-0000000000c1";
export const BROKER = "e2e00000-0000-4000-8000-0000000000b1";
export const BROKER_NAME = "E2E broker";

export const PAIRS = ["EUR/GBP", "GBP/JPY"] as const;
const BAR = 15 * 60_000;

export async function seedMarket(sql: postgres.Sql, now = new Date()) {
  await clearMarket(sql);
  const [eur] = await sql<{ id: string }[]>`insert into instruments (symbol, provider_code, pip_size, display_decimals, sort_order)
    values (${PAIRS[0]}, 'EUR_GBP', 0.0001, 5, 90) returning id`;
  const [jpy] = await sql<{ id: string }[]>`insert into instruments (symbol, provider_code, pip_size, display_decimals, sort_order)
    values (${PAIRS[1]}, 'GBP_JPY', 0.01, 3, 91) returning id`;
  if (!eur || !jpy) throw new Error("could not add the test pairs");
  const day = now.toISOString().slice(0, 10);
  const barTs = new Date(Math.floor((now.getTime() - 50 * 60_000) / BAR) * BAR);

  await sql`insert into brokers (id, name, platform_url_template) values (${BROKER}, ${BROKER_NAME}, 'https://trade.example.com/chart?symbol={symbol}')`;
  await sql`insert into broker_spreads (broker_id, instrument_id, typical_spread_pips) values (${BROKER}, ${eur.id}, 1.0), (${BROKER}, ${jpy.id}, 1.6)`;

  // 15-minute candles around the trigger bar.
  const candles = [];
  let price = 0.8622;
  for (let i = -40; i <= 3; i++) {
    const ts = new Date(barTs.getTime() + i * BAR);
    const o = price;
    const c = price + Math.sin(i / 3) * 0.0006 + (i > -10 ? 0.0002 : -0.0001);
    candles.push({ instrument_id: eur.id, granularity: "M15", ts, o, h: Math.max(o, c) + 0.0003, l: Math.min(o, c) - 0.0003, c });
    price = c;
  }
  await sql`insert into candles ${sql(candles)}`;
  await sql`insert into levels (instrument_id, trading_day, set_kind, data) values
    (${eur.id}, ${day}, 'daily', ${sql.json({ P: 0.8632, R1: 0.8661, R2: 0.8693, R3: 0.8722, S1: 0.86, S2: 0.8571, S3: 0.8539, source: "e2e" })}),
    (${eur.id}, ${day}, 'prev_day', ${sql.json({ PDH: 0.8674, PDL: 0.8612, PDC: 0.863, source: "e2e" })}),
    (${jpy.id}, ${day}, 'fib_pivot', ${sql.json({ pivot: 199.52, up: { break: 200.07, confirmation: 200.41, take_profit: 200.96, reset: 201.85 }, down: { break: 198.97, confirmation: 198.63, take_profit: 198.08, reset: 197.19 }, fib: 55, range_units: "66" })})`;

  const gates = [
    { key: "three_eight.trading_window", passed: true, detail: { window: "primary", close_time: "09:00" } },
    { key: "three_eight.min_indicators", passed: true, detail: { count: 4, minimum: 3 } },
  ];
  // Every row lists the same columns: a multi-row insert takes them from the first row.
  await sql`insert into signals ${sql([
    {
      id: SIGNAL_38, strategy: "three_eight", instrument_id: eur.id, direction: "long", state: "confirmed",
      bar_ts: barTs, trading_day: day, entry: 0.8642, stop: 0.8619, target: 0.8705, alt_target: 0.8722,
      risk_pips: 23, reward_pips: 63, reward_risk: 2.739, indicator_count: 4, has_provisional: true,
      is_countertrend: false, range_mode: false, version_set: sql.json({ "three_eight.pivot_touch": 1 }),
      context: sql.json({ trend: "up", trigger: "daily.S1", explanation: "Long at the daily S1 with 4 of 8 indicators in an uptrend.", minimum: 3, gates }),
      dedupe_key: "e2e:38", created_at: new Date(barTs.getTime() + BAR), closed_at: null, exit_price: null, result_pips: null,
    },
    {
      id: SIGNAL_FIB, strategy: "fib_pivot", instrument_id: jpy.id, direction: "short", state: "open",
      bar_ts: barTs, trading_day: day, entry: 198.97, stop: 199.52, target: 198.08, alt_target: null,
      risk_pips: 55, reward_pips: 89, reward_risk: 1.618, indicator_count: null, has_provisional: false,
      is_countertrend: false, range_mode: false, version_set: sql.json({ "fib_pivot.entry": 1 }),
      context: sql.json({ explanation: "Short on a close below the lower Break at 198.970. Stop at Pivot, target at Take Profit.", gates: [] }),
      dedupe_key: "e2e:fib", created_at: new Date(barTs.getTime() + 2 * BAR), closed_at: null, exit_price: null, result_pips: null,
    },
    {
      id: SIGNAL_CLOSED, strategy: "three_eight", instrument_id: eur.id, direction: "short", state: "target_hit",
      bar_ts: new Date(barTs.getTime() - 20 * BAR), trading_day: day, entry: 0.8661, stop: 0.8684, target: 0.862, alt_target: null,
      risk_pips: 23, reward_pips: 41, reward_risk: 1.783, indicator_count: 3, has_provisional: false,
      is_countertrend: false, range_mode: false, version_set: sql.json({}), context: sql.json({ gates: [] }),
      dedupe_key: "e2e:closed", created_at: new Date(barTs.getTime() - 19 * BAR),
      closed_at: new Date(barTs.getTime() - 5 * BAR), exit_price: 0.862, result_pips: 41,
    },
  ])}`;
  const ind = (key: string, fired: boolean, provisional = false, level_ref: string | null = null, detail = {}) => ({
    signal_id: SIGNAL_38, key, version: 1, fired, counted: fired, provisional, level_ref, detail: sql.json(detail),
  });
  await sql`insert into signal_indicators ${sql([
    ind("three_eight.candlestick", true, false, null, { pattern: "hammer" }),
    ind("three_eight.hl_failure", false),
    ind("three_eight.pivot_touch", true, false, "daily.S1", { level: 0.86 }),
    ind("three_eight.flag_pennant_triangle", false, true),
    ind("three_eight.trendline_channel", true, true, null, { touches: 3 }),
    ind("three_eight.pdh", false),
    ind("three_eight.pdl", true, false, "prev_day.PDL", { level: 0.8612 }),
    ind("three_eight.fibonacci", false),
  ])}`;
  await sql`insert into signal_indicators (signal_id, key, version, fired, counted, provisional, level_ref, detail)
    values (${SIGNAL_FIB}, 'fib_pivot.entry', 1, true, false, false, 'fib.down.break', ${sql.json({ level: 198.97, trigger: "close" })})`;
  await sql`insert into signal_events (signal_id, at, kind, price, note) values
    (${SIGNAL_38}, ${new Date(barTs.getTime() + BAR)}, 'created', 0.8642, 'Long at the daily S1'),
    (${SIGNAL_38}, ${new Date(barTs.getTime() + 2 * BAR)}, 'confirmed', 0.8651, null),
    (${SIGNAL_FIB}, ${new Date(barTs.getTime() + 2 * BAR)}, 'created', 198.97, null),
    (${SIGNAL_CLOSED}, ${new Date(barTs.getTime() - 19 * BAR)}, 'created', 0.8661, null),
    (${SIGNAL_CLOSED}, ${new Date(barTs.getTime() - 5 * BAR)}, 'target_hit', 0.862, null)`;

  await sql`insert into job_runs (job, started_at, finished_at, ok, detail)
    values ('stock_eod', ${now}, ${now}, true, ${sql.json({ ready: true, session: "2026-10-06", digest: ["AAA", "BBB", "CCC"], e2e: true })})`;
  const market = {
    at: now.toISOString(), forex_open: true, trading_day: day, window_enabled: true, window: "primary",
    windows: [{ start: "00:00", end: "10:30" }], in_window: true, next_open: null, stale: ["GBP/USD"],
  };
  await sql`insert into worker_heartbeat (id, at, version, market) values (true, ${now}, 'e2e', ${sql.json(market)})
    on conflict (id) do update set at = excluded.at, version = excluded.version, market = excluded.market`;
}

export async function clearMarket(sql: postgres.Sql) {
  const pairs = await sql<{ id: string }[]>`select id from instruments where symbol in ${sql([...PAIRS])}`;
  const ids = pairs.map((p) => p.id);
  if (ids.length) {
    await sql`delete from signals where instrument_id in ${sql(ids)}`;
    // Candles, levels, and broker spreads cascade with the instrument.
    await sql`delete from instruments where id in ${sql(ids)}`;
  }
  await sql`delete from brokers where id = ${BROKER}`;
  await sql`delete from job_runs where detail->>'e2e' = 'true'`;
}
