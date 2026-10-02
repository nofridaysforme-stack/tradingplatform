import "server-only";
import { and, asc, desc, eq, gte, inArray, lte, sql as dsql } from "drizzle-orm";
import { adjust, brokerLink } from "@/lib/broker-adjust";
import { db } from "@/lib/db";
import {
  brokerSpreads,
  brokers,
  candles,
  instruments,
  jobRuns,
  levels,
  ruleDefinitions,
  ruleVersions,
  signalEvents,
  signalIndicators,
  signals,
  workerHeartbeat,
  type Direction,
  type SignalState,
  type Strategy,
} from "@/lib/db/schema";

// Reads what the scanner wrote. Nothing here decides whether a signal fires (CLAUDE.md rule 1).

export const LIVE_STATES: SignalState[] = ["open", "confirmed"];

export interface Broker {
  id: string;
  name: string;
  platformUrlTemplate: string | null;
}

export interface Prices {
  entry: string;
  stop: string;
  target: string;
  reward_risk: number;
}

/** Spec 14 signal list item, plus display decimals. */
export interface SignalListItem {
  id: string;
  strategy: Strategy;
  instrument: string;
  decimals: number;
  direction: Direction;
  state: SignalState;
  created_at: string;
  indicator_count: number | null;
  indicators_fired: string[];
  provisional_fired: string[];
  has_provisional: boolean;
  confluence: boolean;
  reference: Prices;
  adjusted: (Prices & { broker: string }) | null;
}

export async function activeBroker(brokerId: string | null): Promise<Broker | null> {
  if (!brokerId) return null;
  const [b] = await db
    .select({ id: brokers.id, name: brokers.name, platformUrlTemplate: brokers.platformUrlTemplate })
    .from(brokers)
    .where(and(eq(brokers.id, brokerId), eq(brokers.active, true)))
    .limit(1);
  return b ?? null;
}

export async function listBrokers(): Promise<Broker[]> {
  return db
    .select({ id: brokers.id, name: brokers.name, platformUrlTemplate: brokers.platformUrlTemplate })
    .from(brokers)
    .where(eq(brokers.active, true))
    .orderBy(asc(brokers.name));
}

type Row = {
  signal: typeof signals.$inferSelect;
  symbol: string;
  pipSize: string;
  decimals: number;
  spread: string | null;
  symbolOverride: string | null;
};

function selectRows(broker: Broker | null) {
  return db
    .select({
      signal: signals,
      symbol: instruments.symbol,
      pipSize: instruments.pipSize,
      decimals: instruments.displayDecimals,
      spread: brokerSpreads.typicalSpreadPips,
      symbolOverride: brokerSpreads.symbolOverride,
    })
    .from(signals)
    .innerJoin(instruments, eq(instruments.id, signals.instrumentId))
    .leftJoin(
      brokerSpreads,
      and(
        eq(brokerSpreads.instrumentId, signals.instrumentId),
        eq(brokerSpreads.brokerId, broker?.id ?? "00000000-0000-0000-0000-000000000000"),
      ),
    );
}

function prices(r: Row, broker: Broker | null): { reference: Prices; adjusted: SignalListItem["adjusted"] } {
  const s = r.signal;
  const d = r.decimals;
  const reference = {
    entry: Number(s.entry).toFixed(d),
    stop: Number(s.stop).toFixed(d),
    target: Number(s.target).toFixed(d),
    reward_risk: Number(s.rewardRisk),
  };
  if (!broker || r.spread === null) return { reference, adjusted: null };
  const a = adjust(s.direction, Number(s.entry), Number(s.stop), Number(s.target), Number(r.spread), Number(r.pipSize), d);
  return {
    reference,
    adjusted: {
      broker: broker.name,
      entry: a.entry.toFixed(d),
      stop: a.stop.toFixed(d),
      target: a.target.toFixed(d),
      reward_risk: a.rewardRisk,
    },
  };
}

export interface SignalFilter {
  states?: SignalState[];
  strategy?: Strategy;
  instrument?: string;
}

export async function listSignals(broker: Broker | null, filter: SignalFilter = {}): Promise<SignalListItem[]> {
  const where = [inArray(signals.state, filter.states ?? LIVE_STATES)];
  if (filter.strategy) where.push(eq(signals.strategy, filter.strategy));
  if (filter.instrument) where.push(eq(instruments.symbol, filter.instrument));
  const rows = await selectRows(broker)
    .where(and(...where))
    .orderBy(desc(signals.createdAt))
    .limit(100);
  if (!rows.length) return [];
  const fired = await db
    .select({ signalId: signalIndicators.signalId, key: signalIndicators.key, provisional: signalIndicators.provisional })
    .from(signalIndicators)
    .where(and(eq(signalIndicators.fired, true), inArray(signalIndicators.signalId, rows.map((r) => r.signal.id))));
  return rows.map((r) => {
    const mine = fired.filter((f) => f.signalId === r.signal.id);
    return {
      id: r.signal.id,
      strategy: r.signal.strategy,
      instrument: r.symbol,
      decimals: r.decimals,
      direction: r.signal.direction,
      state: r.signal.state,
      created_at: r.signal.createdAt.toISOString(),
      indicator_count: r.signal.indicatorCount,
      indicators_fired: mine.map((f) => f.key),
      provisional_fired: mine.filter((f) => f.provisional).map((f) => f.key),
      has_provisional: r.signal.hasProvisional,
      confluence: typeof r.signal.context.confluence === "string",
      ...prices(r, broker),
    };
  });
}

export interface SignalDetail extends SignalListItem {
  bar_ts: string;
  trading_day: string;
  alt_target: string | null;
  risk_pips: number;
  reward_pips: number;
  is_countertrend: boolean;
  range_mode: boolean;
  version_set: Record<string, number>;
  explanation: string | null;
  minimum: number | null;
  closed_at: string | null;
  exit_price: string | null;
  result_pips: number | null;
  adjusted_result_pips: number | null;
  broker_link: string | null;
  confluence_id: string | null;
  indicators: {
    key: string;
    name: string;
    version: number;
    fired: boolean;
    counted: boolean;
    provisional: boolean;
    level_ref: string | null;
    detail: Record<string, unknown>;
  }[];
  gates: { key: string; name: string; passed: boolean; detail: Record<string, unknown> }[];
  events: { id: number; at: string; kind: string; price: string | null; note: string | null }[];
  candles: { time: number; open: number; high: number; low: number; close: number }[];
  levels: { label: string; price: number; kind: "pivot" | "prev_day" | "fib" }[];
}

const CHART_BARS_BEFORE = 48;
const CHART_BARS_AFTER = 48;
const BAR_MS = 15 * 60_000;

export async function getSignal(id: string, broker: Broker | null): Promise<SignalDetail | null> {
  const [r] = await selectRows(broker).where(eq(signals.id, id)).limit(1);
  if (!r) return null;
  const s = r.signal;
  const ctx = s.context;
  const [inds, events, bars, lvls, names] = await Promise.all([
    db.select().from(signalIndicators).where(eq(signalIndicators.signalId, id)),
    db.select().from(signalEvents).where(eq(signalEvents.signalId, id)).orderBy(asc(signalEvents.at), asc(signalEvents.id)),
    db
      .select({ ts: candles.ts, o: candles.o, h: candles.h, l: candles.l, c: candles.c })
      .from(candles)
      .where(
        and(
          eq(candles.instrumentId, s.instrumentId),
          eq(candles.granularity, "M15"),
          gte(candles.ts, new Date(s.barTs.getTime() - CHART_BARS_BEFORE * BAR_MS)),
          lte(candles.ts, new Date(s.barTs.getTime() + CHART_BARS_AFTER * BAR_MS)),
        ),
      )
      .orderBy(asc(candles.ts)),
    db
      .select({ setKind: levels.setKind, data: levels.data })
      .from(levels)
      .where(and(eq(levels.instrumentId, s.instrumentId), eq(levels.tradingDay, s.tradingDay))),
    db.select({ key: ruleDefinitions.key, name: ruleDefinitions.name }).from(ruleDefinitions).where(eq(ruleDefinitions.strategy, s.strategy)),
  ]);
  const name = new Map(names.map((n) => [n.key, n.name]));
  const base = prices(r, broker);
  const fired = inds.filter((i) => i.fired);
  const rawGates = Array.isArray(ctx.gates) ? (ctx.gates as { key: string; passed: boolean; detail?: Record<string, unknown> }[]) : [];
  const resultPips = s.resultPips === null ? null : Number(s.resultPips);
  const spreadPips = r.spread === null ? null : Number(r.spread);
  return {
    id: s.id,
    strategy: s.strategy,
    instrument: r.symbol,
    decimals: r.decimals,
    direction: s.direction,
    state: s.state,
    created_at: s.createdAt.toISOString(),
    indicator_count: s.indicatorCount,
    indicators_fired: fired.map((i) => i.key),
    provisional_fired: fired.filter((i) => i.provisional).map((i) => i.key),
    has_provisional: s.hasProvisional,
    confluence: typeof ctx.confluence === "string",
    confluence_id: typeof ctx.confluence === "string" ? ctx.confluence : null,
    ...base,
    bar_ts: s.barTs.toISOString(),
    trading_day: s.tradingDay,
    alt_target: s.altTarget === null ? null : Number(s.altTarget).toFixed(r.decimals),
    risk_pips: Number(s.riskPips),
    reward_pips: Number(s.rewardPips),
    is_countertrend: s.isCountertrend,
    range_mode: s.rangeMode,
    version_set: s.versionSet,
    explanation: typeof ctx.explanation === "string" ? ctx.explanation : null,
    minimum: typeof ctx.minimum === "number" ? ctx.minimum : null,
    closed_at: s.closedAt?.toISOString() ?? null,
    exit_price: s.exitPrice === null ? null : Number(s.exitPrice).toFixed(r.decimals),
    result_pips: resultPips,
    // A closed trade pays the full spread once (half on entry, half on exit).
    adjusted_result_pips: resultPips !== null && spreadPips !== null && broker ? Math.round((resultPips - spreadPips) * 10) / 10 : null,
    broker_link: broker && spreadPips !== null ? brokerLink(broker.platformUrlTemplate, r.symbol, r.symbolOverride) : null,
    indicators: inds.map((i) => ({
      key: i.key,
      name: name.get(i.key) ?? i.key,
      version: i.version,
      fired: i.fired,
      counted: i.counted,
      provisional: i.provisional,
      level_ref: i.levelRef,
      detail: i.detail,
    })),
    gates: rawGates.map((g) => ({ key: g.key, name: name.get(g.key) ?? g.key, passed: g.passed, detail: g.detail ?? {} })),
    events: events.map((e) => ({ id: e.id, at: e.at.toISOString(), kind: e.kind, price: e.price === null ? null : Number(e.price).toFixed(r.decimals), note: e.note })),
    candles: bars.map((b) => ({ time: b.ts.getTime() / 1000, open: Number(b.o), high: Number(b.h), low: Number(b.l), close: Number(b.c) })),
    levels: chartLevels(s.strategy, lvls),
  };
}

function chartLevels(strategy: Strategy, sets: { setKind: string; data: Record<string, unknown> }[]): SignalDetail["levels"] {
  const out: SignalDetail["levels"] = [];
  const num = (v: unknown) => (typeof v === "number" || typeof v === "string" ? Number(v) : NaN);
  for (const set of sets) {
    if (set.setKind === "daily" && strategy === "three_eight") {
      for (const k of ["R3", "R2", "R1", "P", "S1", "S2", "S3"]) {
        const p = num(set.data[k]);
        if (Number.isFinite(p)) out.push({ label: k, price: p, kind: "pivot" });
      }
    }
    if (set.setKind === "prev_day" && strategy === "three_eight") {
      for (const k of ["PDH", "PDL"]) {
        const p = num(set.data[k]);
        if (Number.isFinite(p)) out.push({ label: k, price: p, kind: "prev_day" });
      }
    }
    if (set.setKind === "fib_pivot" && strategy === "fib_pivot") {
      const pivot = num(set.data.pivot);
      if (Number.isFinite(pivot)) out.push({ label: "Pivot", price: pivot, kind: "pivot" });
      for (const [side, mark] of [["up", "+"], ["down", "-"]] as const) {
        const ladder = set.data[side] as Record<string, unknown> | undefined;
        for (const [k, label] of [["break", "Break"], ["confirmation", "Confirmation"], ["take_profit", "Take profit"], ["reset", "Reset"]] as const) {
          const p = num(ladder?.[k]);
          if (Number.isFinite(p)) out.push({ label: `${label} ${mark}`, price: p, kind: "fib" });
        }
      }
    }
  }
  return out;
}

export interface DailyGoal {
  pips: number;
  signals: number;
  min: number;
  max: number;
}

/** Pips from today's closed 3/8 signals against the target band in the three_eight.target
 *  rule (spec 13). Today is the trading day the worker last reported. */
export async function dailyGoal(tradingDay: string | null): Promise<DailyGoal | null> {
  if (!tradingDay) return null;
  const [rule] = await db
    .select({ params: ruleVersions.params })
    .from(ruleVersions)
    .innerJoin(ruleDefinitions, and(eq(ruleDefinitions.key, ruleVersions.key), eq(ruleDefinitions.currentVersion, ruleVersions.version)))
    .where(eq(ruleVersions.key, "three_eight.target"))
    .limit(1);
  const min = Number(rule?.params.daily_target_min_pips);
  const max = Number(rule?.params.daily_target_max_pips);
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= 0) return null;
  const [row] = await db
    .select({ pips: dsql<string>`coalesce(sum(${signals.resultPips}), 0)`, n: dsql<number>`count(*)::int` })
    .from(signals)
    .where(
      and(
        eq(signals.strategy, "three_eight"),
        eq(signals.tradingDay, tradingDay),
        inArray(signals.state, ["target_hit", "stop_hit", "expired"]),
      ),
    );
  return { pips: Number(row?.pips ?? 0), signals: row?.n ?? 0, min, max };
}

export interface StockDigest {
  count: number;
  session: string;
}

/** The newly confirmed stocks from the last completed screen (written by the stock_eod job). */
export async function stockDigest(): Promise<StockDigest | null> {
  const [run] = await db
    .select({ detail: jobRuns.detail })
    .from(jobRuns)
    .where(and(eq(jobRuns.job, "stock_eod"), eq(jobRuns.ok, true), dsql`${jobRuns.detail} ? 'digest'`))
    .orderBy(desc(jobRuns.startedAt))
    .limit(1);
  const digest = run?.detail?.digest;
  const session = run?.detail?.session;
  if (!Array.isArray(digest) || typeof session !== "string") return null;
  return { count: digest.length, session };
}

export async function heartbeat() {
  const [hb] = await db.select().from(workerHeartbeat).limit(1);
  return hb ?? null;
}
