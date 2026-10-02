import "server-only";
import { and, asc, count, eq, gte, inArray, lte, notInArray, type SQL } from "drizzle-orm";
import { z } from "zod";
import { db } from "@/lib/db";
import { instruments, signals, type SignalState } from "@/lib/db/schema";
import { cumulative, summarize, type Summary } from "@/lib/metrics";

// Closed signals with filters (spec 13 History, spec 14 /api/history). Metrics leave out
// invalidated signals, like the backtest.

export const OUTCOMES = ["target_hit", "stop_hit", "expired", "ambiguous", "invalidated"] as const satisfies SignalState[];
export const PAGE_SIZE = 50;

const empty = z.literal("").transform(() => undefined);

export const HistoryFilter = z.object({
  from: z.iso.date().optional().or(empty),
  to: z.iso.date().optional().or(empty),
  strategy: z.enum(["three_eight", "fib_pivot"]).optional().or(empty),
  instrument: z.string().max(20).optional().or(empty),
  direction: z.enum(["long", "short"]).optional().or(empty),
  outcome: z.enum(OUTCOMES).optional().or(empty),
  provisional: z.enum(["yes", "no"]).optional().or(empty),
  page: z.coerce.number().int().min(1).max(10_000).optional().or(empty),
});
export type HistoryFilter = z.infer<typeof HistoryFilter>;

/** Parse URL search params; anything invalid falls back to "no filter" for that field. */
export function parseFilter(params: Record<string, string | string[] | undefined>): HistoryFilter {
  const flat = Object.fromEntries(Object.entries(params).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]));
  const out: Record<string, unknown> = {};
  for (const [key, schema] of Object.entries(HistoryFilter.shape)) {
    const r = schema.safeParse(flat[key]);
    if (r.success && r.data !== undefined) out[key] = r.data;
  }
  return out as HistoryFilter;
}

export function filterQuery(f: HistoryFilter, page?: number): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) if (v !== undefined && k !== "page") q.set(k, String(v));
  if (page && page > 1) q.set("page", String(page));
  const s = q.toString();
  return s ? `?${s}` : "";
}

function where(f: HistoryFilter): SQL | undefined {
  const w: SQL[] = [notInArray(signals.state, ["open", "confirmed"])];
  if (f.from) w.push(gte(signals.tradingDay, f.from));
  if (f.to) w.push(lte(signals.tradingDay, f.to));
  if (f.strategy) w.push(eq(signals.strategy, f.strategy));
  if (f.instrument) w.push(eq(instruments.symbol, f.instrument));
  if (f.direction) w.push(eq(signals.direction, f.direction));
  if (f.outcome) w.push(inArray(signals.state, [f.outcome]));
  if (f.provisional) w.push(eq(signals.hasProvisional, f.provisional === "yes"));
  return and(...w);
}

export interface HistoryRow {
  id: string;
  trading_day: string;
  closed_at: string | null;
  strategy: "three_eight" | "fib_pivot";
  instrument: string;
  direction: "long" | "short";
  outcome: SignalState;
  result_pips: number | null;
  reward_risk: number;
  has_provisional: boolean;
  version_set: Record<string, number>;
}

const COLUMNS = {
  id: signals.id,
  tradingDay: signals.tradingDay,
  closedAt: signals.closedAt,
  createdAt: signals.createdAt,
  strategy: signals.strategy,
  instrument: instruments.symbol,
  direction: signals.direction,
  state: signals.state,
  resultPips: signals.resultPips,
  rewardRisk: signals.rewardRisk,
  hasProvisional: signals.hasProvisional,
  versionSet: signals.versionSet,
};

const base = () => db.select(COLUMNS).from(signals).innerJoin(instruments, eq(instruments.id, signals.instrumentId));
type Raw = Awaited<ReturnType<typeof base>>[number];

const toRow = (r: Raw): HistoryRow => ({
  id: r.id,
  trading_day: r.tradingDay,
  closed_at: r.closedAt?.toISOString() ?? null,
  strategy: r.strategy,
  instrument: r.instrument,
  direction: r.direction,
  outcome: r.state,
  result_pips: r.resultPips === null ? null : Number(r.resultPips),
  reward_risk: Number(r.rewardRisk),
  has_provisional: r.hasProvisional,
  version_set: r.versionSet,
});

/** Every matching closed signal, oldest close first (for metrics, the chart, and CSV). */
export async function allRows(f: HistoryFilter): Promise<HistoryRow[]> {
  const rows = await base()
    .where(where(f))
    .orderBy(asc(signals.closedAt), asc(signals.createdAt), asc(signals.id));
  return rows.map(toRow);
}

export interface HistoryPage {
  rows: HistoryRow[];
  page: number;
  pages: number;
  total: number;
  summary: Summary;
  curve: { at: string; pips: number }[];
}

export async function historyPage(f: HistoryFilter): Promise<HistoryPage> {
  const all = await allRows(f);
  const trades = all.filter((r) => r.result_pips !== null).map((r) => ({ state: r.outcome, resultPips: r.result_pips ?? 0, closedAt: r.closed_at ?? r.trading_day }));
  const pages = Math.max(1, Math.ceil(all.length / PAGE_SIZE));
  const page = Math.min(f.page ?? 1, pages);
  // Newest first in the table.
  const newest = [...all].reverse();
  return {
    rows: newest.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    page,
    pages,
    total: all.length,
    summary: summarize(trades),
    curve: cumulative(trades),
  };
}

export async function instrumentSymbols(): Promise<string[]> {
  const rows = await db
    .select({ symbol: instruments.symbol, n: count(signals.id) })
    .from(instruments)
    .leftJoin(signals, eq(signals.instrumentId, instruments.id))
    .groupBy(instruments.symbol, instruments.sortOrder)
    .orderBy(asc(instruments.sortOrder), asc(instruments.symbol));
  return rows.map((r) => r.symbol);
}

