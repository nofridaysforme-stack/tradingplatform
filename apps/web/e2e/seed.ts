import type postgres from "postgres";

// Signals, levels, candles, and a heartbeat in the shapes the scanner writes, for the
// end-to-end tests and local screenshots. Everything hangs off two test pairs that are not
// in the seeded set (EUR/GBP, GBP/JPY), so clearing them never touches real market data.

export const SIGNAL_38 = "e2e00000-0000-4000-8000-000000000038";
export const SIGNAL_FIB = "e2e00000-0000-4000-8000-0000000000f1";
export const SIGNAL_CLOSED = "e2e00000-0000-4000-8000-0000000000c1";
export const SIGNAL_LOSS = "e2e00000-0000-4000-8000-0000000000c2";
export const SIGNAL_VOID = "e2e00000-0000-4000-8000-0000000000c3";
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
    (${eur.id}, ${day}, 'weekly', ${sql.json({ P: 0.8651, R1: 0.8702, R2: 0.8744, R3: 0.8795, S1: 0.8609, S2: 0.8558, S3: 0.8516, source: "e2e" })}),
    (${eur.id}, ${day}, 'monthly', ${sql.json({ P: 0.8588, R1: 0.8701, R2: 0.8790, R3: 0.8903, S1: 0.8499, S2: 0.8386, S3: 0.8297, source: "e2e" })}),
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
  // Older closed signals for History: a loss the day before and an invalidated signal.
  const yesterday = new Date(now.getTime() - 86_400_000).toISOString().slice(0, 10);
  const older = (id: string, inst: string, state: string, result: number, d: string, provisional: boolean, hoursAgo: number) => ({
    id, strategy: inst === jpy.id ? "fib_pivot" : "three_eight", instrument_id: inst, direction: "short", state,
    bar_ts: new Date(now.getTime() - hoursAgo * 3_600_000), trading_day: d,
    entry: inst === jpy.id ? 198.97 : 0.8661, stop: inst === jpy.id ? 199.52 : 0.8684, target: inst === jpy.id ? 198.08 : 0.862, alt_target: null,
    risk_pips: inst === jpy.id ? 55 : 23, reward_pips: inst === jpy.id ? 89 : 41, reward_risk: inst === jpy.id ? 1.618 : 1.783,
    indicator_count: inst === jpy.id ? null : 3, has_provisional: provisional, is_countertrend: false, range_mode: false,
    version_set: sql.json({ "three_eight.pivot_touch": 1, "three_eight.trendline_channel": 1 }), context: sql.json({ gates: [] }),
    dedupe_key: `e2e:${id}`, created_at: new Date(now.getTime() - hoursAgo * 3_600_000),
    closed_at: new Date(now.getTime() - (hoursAgo - 2) * 3_600_000), exit_price: null, result_pips: result,
  });
  await sql`insert into signals ${sql([
    older(SIGNAL_LOSS, jpy.id, "stop_hit", -55, yesterday, true, 26),
    older(SIGNAL_VOID, eur.id, "invalidated", -10, yesterday, false, 24),
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
  await seedStocks(sql);
  const nextWeek = new Date(now.getTime() + 3 * 86_400_000);
  const lastWeek = new Date(now.getTime() - 2 * 86_400_000);
  await sql`insert into econ_events (at, currency, title, impact) values
    (${nextWeek}, 'USD', 'E2E Nonfarm payrolls', 'high'), (${lastWeek}, 'EUR', 'E2E ECB rate decision', 'high')`;
  await sql`insert into worker_heartbeat (id, at, version, market) values (true, ${now}, 'e2e', ${sql.json(market)})
    on conflict (id) do update set at = excluded.at, version = excluded.version, market = excluded.market`;
}

export const STOCKS = ["E2EA", "E2EB", "E2EC"] as const;
export const SESSION = "2026-09-30";
export const PREV_SESSION = "2026-09-29";

function weekdays(end: string, count: number): string[] {
  const out: string[] = [];
  const d = new Date(`${end}T12:00:00Z`);
  while (out.length < count) {
    if (d.getUTCDay() !== 0 && d.getUTCDay() !== 6) out.unshift(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() - 1);
  }
  return out;
}

/** Three made-up tickers with bars and two sessions of screen results. */
export async function seedStocks(sql: postgres.Sql) {
  await clearStocks(sql);
  await sql`insert into stock_tickers (ticker, name, exchange) values
    ('E2EA', 'E2E Alpha Industries', 'XNYS'), ('E2EB', 'E2E Beta Labs', 'XNAS'), ('E2EC', 'E2E Gamma Retail', 'XNAS')`;
  const days = weekdays(SESSION, 60);
  const bars = STOCKS.flatMap((ticker, k) =>
    days.map((d, i) => {
      const c = [30 + i * 0.35, 18 + i * 0.2, 12 + Math.sin(i / 4)][k]!;
      return { ticker, session_date: d, o: c - 0.2, h: c + 0.4, l: c - 0.5, c, volume: 500_000 + i * 1000 };
    }),
  );
  await sql`insert into stock_daily_bars ${sql(bars)}`;
  const versions = sql.json({ "stocks.rule1_near_high": 1, "stocks.rule2_double": 1, "stocks.rule3_apr": 1 });
  const row = (session_date: string, ticker: string, status: string, close: number, high: number, low: number, closes: [number, number, number, number], consistent: boolean) => {
    const acc = closes.map((x) => (close - x) / x);
    const apr = acc.map((a, i) => (a / [5, 10, 20, 50][i]!) * 260);
    return {
      session_date, ticker, status, close, high_52w: high, low_52w: low, apr_52w: (high - low) / low,
      close_5: closes[0], close_10: closes[1], close_20: closes[2], close_50: closes[3],
      acc_5: acc[0], acc_10: acc[1], acc_20: acc[2], acc_50: acc[3],
      apr_5: apr[0], apr_10: apr[1], apr_20: apr[2], apr_50: apr[3],
      consistent, version_set: versions,
    };
  };
  await sql`insert into stock_screen_results ${sql([
    { ...row(PREV_SESSION, "E2EA", "qualified", 50.3, 52, 20, [48.5, 46.8, 43.4, 50.6], false), momentum: true, watching: true, indicators: null },
    { ...row(SESSION, "E2EA", "trend_confirmed", 50.65, 52, 20, [48.9, 47.2, 43.7, 33.9], true), momentum: false, watching: false, indicators: sql.json(evidence(1)) },
    { ...row(SESSION, "E2EB", "qualified", 29.8, 32, 14, [30.1, 29, 26, 31], false), momentum: true, watching: true, indicators: sql.json(evidence(2)) },
    { ...row(SESSION, "E2EC", "trend_established", 12.5, 13.5, 6, [12.9, 12.2, 11.4, 13.1], false), momentum: false, watching: false, indicators: null },
  ])}`;
  // Spec 08 buys: one open on E2EA (bought on the watch list), one sold on E2EC.
  const [open] = await sql<{ id: string }[]>`insert into stock_signals ${sql({
    ticker: "E2EA", buy_session: PREV_SESSION, entry: 50.3, stop_initial: 47.79, projection: 67.91, projection_pct: 35,
    horizon_sessions: 20, state: "open", trailing_active: false, highest_close: 50.65, stop_now: 47.79, last_session: SESSION,
    votes: sql.json(buyVotes), version_set: versions, has_provisional: true,
  })} returning id`;
  const [sold] = await sql<{ id: string }[]>`insert into stock_signals ${sql({
    ticker: "E2EC", buy_session: "2026-09-10", entry: 11, stop_initial: 10.45, projection: 14.85, projection_pct: 35,
    horizon_sessions: 20, state: "sold", trailing_active: true, highest_close: 13.2, stop_now: 12.54, last_session: "2026-09-29",
    exit_session: "2026-09-29", exit_price: 12.9, result_pct: 0.172727, votes: sql.json(buyVotes),
    exit_votes: sql.json(sellVotes), version_set: versions, has_provisional: false,
  })} returning id`;
  await sql`insert into stock_signal_events ${sql([
    { signal_id: open!.id, session: PREV_SESSION, kind: "bought", price: 50.3, detail: sql.json({}) },
    { signal_id: sold!.id, session: "2026-09-10", kind: "bought", price: 11, detail: sql.json({}) },
    { signal_id: sold!.id, session: "2026-09-21", kind: "trailing_started", price: 12.2, detail: sql.json({}) },
    { signal_id: sold!.id, session: "2026-09-29", kind: "sold", price: 12.9, detail: sql.json({}) },
  ])}`;
}

const IND = ["stocks.ind_candle", "stocks.ind_macd", "stocks.ind_pivot", "stocks.ind_rsi", "stocks.ind_stoch"] as const;
const vote = (fired: boolean, session?: string, extra: Record<string, unknown> = {}) => ({ enabled: true, fired, provisional: false, ...(fired ? { session } : {}), ...extra });
const buyVotes = {
  "stocks.ind_candle": vote(true, PREV_SESSION, { patterns: ["engulfing"], provisional: true }),
  "stocks.ind_macd": vote(true, PREV_SESSION, { values: { macd: 0.42, signal: 0.31 } }),
  "stocks.ind_pivot": vote(true, "2026-09-26"),
  "stocks.ind_rsi": vote(false, undefined, { provisional: true }),
  "stocks.ind_stoch": vote(false, undefined, { provisional: true }),
};
const sellVotes = Object.fromEntries(IND.map((k, i) => [k, vote(i < 3, "2026-09-29")]));
/** A screen result's evidence with the first `n` buy indicators fired. */
function evidence(n: number) {
  const side = (fired: number) =>
    Object.fromEntries(IND.map((k, i) => [k, vote(i < fired, SESSION, { values: k === "stocks.ind_rsi" ? { rsi: 48.2 } : {}, provisional: k === "stocks.ind_rsi" })]));
  return { buy: side(n), sell: side(0), momentum: { enabled: true, period: 10, rate: n === 2 ? 5.12 : 0.9, threshold: 4.55, passed: n === 2 } };
}

export async function clearStocks(sql: postgres.Sql) {
  await sql`delete from stock_signals where ticker in ${sql([...STOCKS])}`;
  await sql`delete from stock_screen_results where ticker in ${sql([...STOCKS])}`;
  await sql`delete from stock_daily_bars where ticker in ${sql([...STOCKS])}`;
  await sql`delete from stock_tickers where ticker in ${sql([...STOCKS])}`;
  await sql`delete from econ_events where title like 'E2E %'`;
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
  await clearStocks(sql);
}
