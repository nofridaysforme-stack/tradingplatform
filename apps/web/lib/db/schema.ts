// Drizzle table definitions for querying the schema in db/migrations (dbmate owns it;
// never generate migrations from this file). Property names for the Auth.js tables follow
// the Auth.js Drizzle adapter; the columns map to the snake_case names in the SQL.
import {
  bigint,
  bigserial,
  boolean,
  date,
  integer,
  jsonb,
  numeric,
  pgTable,
  primaryKey,
  smallint,
  text,
  time,
  timestamp,
  uuid,
} from "drizzle-orm/pg-core";

const tz = (name: string) => timestamp(name, { withTimezone: true, mode: "date" });

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  email: text("email").notNull().unique(),
  name: text("name"),
  role: text("role").$type<"owner" | "admin">().notNull().default("owner"),
  active: boolean("active").notNull().default(true),
  timezone: text("timezone").notNull().default("America/New_York"),
  activeBrokerId: uuid("active_broker_id"),
  acknowledgedNoticeAt: tz("acknowledged_notice_at"),
  createdAt: tz("created_at").notNull().defaultNow(),
  emailVerified: tz("email_verified"),
  image: text("image"),
});

export const accounts = pgTable(
  "accounts",
  {
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    type: text("type").notNull(),
    provider: text("provider").notNull(),
    providerAccountId: text("provider_account_id").notNull(),
    refresh_token: text("refresh_token"),
    access_token: text("access_token"),
    expires_at: integer("expires_at"),
    token_type: text("token_type"),
    scope: text("scope"),
    id_token: text("id_token"),
    session_state: text("session_state"),
  },
  (t) => [primaryKey({ columns: [t.provider, t.providerAccountId] })],
);

export const sessions = pgTable("sessions", {
  sessionToken: text("session_token").primaryKey(),
  userId: uuid("user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  expires: tz("expires").notNull(),
});

export const verificationTokens = pgTable(
  "verification_tokens",
  {
    identifier: text("identifier").notNull(),
    token: text("token").notNull(),
    expires: tz("expires").notNull(),
  },
  (t) => [primaryKey({ columns: [t.identifier, t.token] })],
);

export const allowlist = pgTable("allowlist", {
  email: text("email").primaryKey(),
  addedBy: uuid("added_by"),
  addedAt: tz("added_at").notNull().defaultNow(),
});

export const auditLog = pgTable("audit_log", {
  id: bigserial("id", { mode: "number" }).primaryKey(),
  at: tz("at").notNull().defaultNow(),
  userId: uuid("user_id"),
  action: text("action").notNull(),
  target: text("target"),
  before: jsonb("before"),
  after: jsonb("after"),
});

// Market data and brokers. Numeric columns come back as strings, so prices keep their exact
// decimals.

export const instruments = pgTable("instruments", {
  id: uuid("id").primaryKey().defaultRandom(),
  symbol: text("symbol").notNull(),
  providerCode: text("provider_code").notNull(),
  assetClass: text("asset_class").notNull(),
  pipSize: numeric("pip_size").notNull(),
  displayDecimals: smallint("display_decimals").notNull(),
  enabled: boolean("enabled").notNull().default(true),
  sortOrder: smallint("sort_order").notNull().default(0),
});

export const brokers = pgTable("brokers", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name").notNull(),
  platformUrlTemplate: text("platform_url_template"),
  notes: text("notes"),
  active: boolean("active").notNull().default(true),
});

export const brokerSpreads = pgTable(
  "broker_spreads",
  {
    brokerId: uuid("broker_id").notNull(),
    instrumentId: uuid("instrument_id").notNull(),
    typicalSpreadPips: numeric("typical_spread_pips").notNull(),
    symbolOverride: text("symbol_override"),
  },
  (t) => [primaryKey({ columns: [t.brokerId, t.instrumentId] })],
);

export const candles = pgTable(
  "candles",
  {
    instrumentId: uuid("instrument_id").notNull(),
    granularity: text("granularity").notNull(),
    ts: tz("ts").notNull(),
    o: numeric("o").notNull(),
    h: numeric("h").notNull(),
    l: numeric("l").notNull(),
    c: numeric("c").notNull(),
  },
  (t) => [primaryKey({ columns: [t.instrumentId, t.granularity, t.ts] })],
);

export const levels = pgTable(
  "levels",
  {
    instrumentId: uuid("instrument_id").notNull(),
    tradingDay: date("trading_day").notNull(),
    setKind: text("set_kind").$type<"daily" | "weekly" | "monthly" | "prev_day" | "fib_pivot">().notNull(),
    data: jsonb("data").$type<Record<string, unknown>>().notNull(),
  },
  (t) => [primaryKey({ columns: [t.instrumentId, t.tradingDay, t.setKind] })],
);

// Rules (read here for names and the daily goal; edited in the rules pages).

export const ruleDefinitions = pgTable("rule_definitions", {
  key: text("key").primaryKey(),
  strategy: text("strategy").$type<Strategy | "stocks">().notNull(),
  kind: text("kind").$type<"indicator" | "gate" | "plan" | "filter" | "lifecycle">().notNull(),
  name: text("name").notNull(),
  source: text("source").notNull(),
  currentVersion: integer("current_version").notNull(),
});

export const ruleVersions = pgTable(
  "rule_versions",
  {
    key: text("key").notNull(),
    version: integer("version").notNull(),
    status: text("status").$type<"approved" | "provisional">().notNull(),
    enabled: boolean("enabled").notNull(),
    countsTowardMinimum: boolean("counts_toward_minimum").notNull(),
    description: text("description").notNull(),
    paramsSchema: jsonb("params_schema").$type<Record<string, { type: string; default?: unknown; min?: number; max?: number; options?: (string | number)[] }>>().notNull(),
    params: jsonb("params").$type<Record<string, unknown>>().notNull(),
    changeNote: text("change_note"),
    createdBy: uuid("created_by"),
    createdAt: tz("created_at").notNull().defaultNow(),
  },
  (t) => [primaryKey({ columns: [t.key, t.version] })],
);

export const strategyParamOverrides = pgTable(
  "strategy_param_overrides",
  {
    key: text("key").notNull(),
    instrumentId: uuid("instrument_id").notNull(),
    params: jsonb("params").$type<Record<string, unknown>>().notNull(),
    updatedBy: uuid("updated_by"),
    updatedAt: tz("updated_at").notNull().defaultNow(),
  },
  (t) => [primaryKey({ columns: [t.key, t.instrumentId] })],
);

export const strategyConfigs = pgTable("strategy_configs", {
  strategy: text("strategy").$type<Strategy | "stocks">().primaryKey(),
  enabled: boolean("enabled").notNull(),
  instrumentIds: uuid("instrument_ids").array(),
  updatedBy: uuid("updated_by"),
  updatedAt: tz("updated_at").notNull().defaultNow(),
});

/** Every rule change bumps this counter; the worker reloads rules when it moves (spec 05). */
export const ruleConfigRevision = pgTable("rule_config_revision", {
  id: boolean("id").primaryKey(),
  revision: bigint("revision", { mode: "number" }).notNull(),
  updatedAt: tz("updated_at").notNull().defaultNow(),
});

// Signals, written by the scanner.

export type Strategy = "three_eight" | "fib_pivot";
export type Direction = "long" | "short";
export type SignalState = "open" | "confirmed" | "target_hit" | "stop_hit" | "expired" | "invalidated" | "ambiguous";

export const signals = pgTable("signals", {
  id: uuid("id").primaryKey(),
  strategy: text("strategy").$type<Strategy>().notNull(),
  instrumentId: uuid("instrument_id").notNull(),
  direction: text("direction").$type<Direction>().notNull(),
  state: text("state").$type<SignalState>().notNull(),
  barTs: tz("bar_ts").notNull(),
  tradingDay: date("trading_day").notNull(),
  entry: numeric("entry").notNull(),
  stop: numeric("stop").notNull(),
  target: numeric("target").notNull(),
  altTarget: numeric("alt_target"),
  riskPips: numeric("risk_pips").notNull(),
  rewardPips: numeric("reward_pips").notNull(),
  rewardRisk: numeric("reward_risk").notNull(),
  indicatorCount: smallint("indicator_count"),
  hasProvisional: boolean("has_provisional").notNull(),
  isCountertrend: boolean("is_countertrend").notNull(),
  rangeMode: boolean("range_mode").notNull(),
  versionSet: jsonb("version_set").$type<Record<string, number>>().notNull(),
  context: jsonb("context").$type<Record<string, unknown>>().notNull(),
  closedAt: tz("closed_at"),
  exitPrice: numeric("exit_price"),
  resultPips: numeric("result_pips"),
  createdAt: tz("created_at").notNull(),
});

export const signalIndicators = pgTable(
  "signal_indicators",
  {
    signalId: uuid("signal_id").notNull(),
    key: text("key").notNull(),
    version: integer("version").notNull(),
    fired: boolean("fired").notNull(),
    counted: boolean("counted").notNull(),
    provisional: boolean("provisional").notNull(),
    levelRef: text("level_ref"),
    detail: jsonb("detail").$type<Record<string, unknown>>().notNull(),
  },
  (t) => [primaryKey({ columns: [t.signalId, t.key] })],
);

export const signalEvents = pgTable("signal_events", {
  id: bigserial("id", { mode: "number" }).primaryKey(),
  signalId: uuid("signal_id").notNull(),
  at: tz("at").notNull().defaultNow(),
  kind: text("kind").notNull(),
  price: numeric("price"),
  note: text("note"),
});

// Worker state.

export const jobRuns = pgTable("job_runs", {
  id: bigserial("id", { mode: "number" }).primaryKey(),
  job: text("job").notNull(),
  startedAt: tz("started_at").notNull(),
  finishedAt: tz("finished_at"),
  ok: boolean("ok"),
  detail: jsonb("detail").$type<Record<string, unknown>>(),
});

export const workerHeartbeat = pgTable("worker_heartbeat", {
  id: boolean("id").primaryKey(),
  at: tz("at").notNull(),
  version: text("version"),
  market: jsonb("market").$type<WorkerMarket>(),
});

/** Written by the worker with each heartbeat (services/scanner/scanner/market_status.py). */
export interface WorkerMarket {
  at: string;
  forex_open: boolean;
  trading_day: string;
  window_enabled: boolean;
  window: "primary" | "alternative" | "both";
  windows: { start: string; end: string }[];
  in_window: boolean;
  next_open: string | null;
  stale: string[];
}

// Stocks (spec 08), written by the stock_eod job; holdings are entered by owners.

export type ScreenStatus = "qualified" | "trend_established" | "trend_confirmed";

export const stockTickers = pgTable("stock_tickers", {
  ticker: text("ticker").primaryKey(),
  name: text("name"),
  exchange: text("exchange"),
  active: boolean("active").notNull(),
});

export const stockDailyBars = pgTable(
  "stock_daily_bars",
  {
    ticker: text("ticker").notNull(),
    sessionDate: date("session_date").notNull(),
    o: numeric("o").notNull(),
    h: numeric("h").notNull(),
    l: numeric("l").notNull(),
    c: numeric("c").notNull(),
    volume: bigint("volume", { mode: "number" }).notNull(),
  },
  (t) => [primaryKey({ columns: [t.ticker, t.sessionDate] })],
);

export const stockScreenResults = pgTable(
  "stock_screen_results",
  {
    sessionDate: date("session_date").notNull(),
    ticker: text("ticker").notNull(),
    status: text("status").$type<ScreenStatus>().notNull(),
    close: numeric("close").notNull(),
    high52w: numeric("high_52w").notNull(),
    low52w: numeric("low_52w").notNull(),
    apr52w: numeric("apr_52w").notNull(),
    close5: numeric("close_5"),
    close10: numeric("close_10"),
    close20: numeric("close_20"),
    close50: numeric("close_50"),
    acc5: numeric("acc_5"),
    acc10: numeric("acc_10"),
    acc20: numeric("acc_20"),
    acc50: numeric("acc_50"),
    apr5: numeric("apr_5"),
    apr10: numeric("apr_10"),
    apr20: numeric("apr_20"),
    apr50: numeric("apr_50"),
    consistent: boolean("consistent").notNull(),
    versionSet: jsonb("version_set").$type<Record<string, number>>().notNull(),
  },
  (t) => [primaryKey({ columns: [t.sessionDate, t.ticker] })],
);

export const holdings = pgTable("holdings", {
  id: uuid("id").primaryKey().defaultRandom(),
  userId: uuid("user_id").notNull(),
  ticker: text("ticker").notNull(),
  purchasePrice: numeric("purchase_price").notNull(),
  purchaseDate: date("purchase_date").notNull(),
  expectedProfitPct: numeric("expected_profit_pct").notNull(),
  horizonSessions: smallint("horizon_sessions").notNull(),
  closed: boolean("closed").notNull().default(false),
  notes: text("notes"),
  createdAt: tz("created_at").notNull().defaultNow(),
});

export const econEvents = pgTable("econ_events", {
  id: uuid("id").primaryKey().defaultRandom(),
  at: tz("at").notNull(),
  currency: text("currency").notNull(),
  title: text("title").notNull(),
  impact: text("impact").$type<"high" | "medium" | "low">().notNull(),
  createdBy: uuid("created_by"),
  createdAt: tz("created_at").notNull().defaultNow(),
});

// Notifications (spec 11). The worker sends; the portal stores preferences, devices, and the
// Telegram link, and queues test notifications.

export type ChannelKind = "webpush" | "email" | "telegram";

export const notificationPrefs = pgTable("notification_prefs", {
  userId: uuid("user_id").primaryKey(),
  channels: text("channels").array().$type<ChannelKind[]>().notNull(),
  strategies: text("strategies").array().$type<("three_eight" | "fib_pivot" | "stocks")[]>().notNull(),
  instrumentIds: uuid("instrument_ids").array(),
  quietStart: time("quiet_start"),
  quietEnd: time("quiet_end"),
  includeUpdates: boolean("include_updates").notNull(),
  updatedAt: tz("updated_at").notNull().defaultNow(),
});

export const pushSubscriptions = pgTable("push_subscriptions", {
  id: uuid("id").primaryKey().defaultRandom(),
  userId: uuid("user_id").notNull(),
  endpoint: text("endpoint").notNull(),
  p256dh: text("p256dh").notNull(),
  auth: text("auth").notNull(),
  userAgent: text("user_agent"),
  createdAt: tz("created_at").notNull().defaultNow(),
});

export const telegramLinks = pgTable("telegram_links", {
  userId: uuid("user_id").primaryKey(),
  chatId: bigint("chat_id", { mode: "number" }),
  linkToken: text("link_token"),
  linkedAt: tz("linked_at"),
});

export const notifications = pgTable("notifications", {
  id: bigserial("id", { mode: "number" }).primaryKey(),
  userId: uuid("user_id"),
  kind: text("kind").notNull(),
  channel: text("channel").$type<ChannelKind>().notNull(),
  status: text("status").notNull().default("queued"),
  error: text("error"),
  payload: jsonb("payload").$type<Record<string, unknown>>().notNull(),
  createdAt: tz("created_at").notNull().defaultNow(),
  sentAt: tz("sent_at"),
});
