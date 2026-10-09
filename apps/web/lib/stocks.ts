import "server-only";
import { and, asc, count, desc, eq, gt, ilike, inArray, ne, or, sql as dsql, type SQL } from "drizzle-orm";
import { z } from "zod";
import { db } from "@/lib/db";
import { INDICATORS } from "@/lib/stock-names";
import {
  ruleVersions,
  stockDailyBars,
  stockScreenResults,
  stockSignalEvents,
  stockSignals,
  stockTickers,
  type DayEvidence,
  type Evidence,
  type ScreenStatus,
  type StockSignalState,
} from "@/lib/db/schema";

// Reads what the stock_eod job wrote (spec 08). Statuses and five-line values come from the
// worker; nothing here re-runs the screen.

export const STATUSES = ["qualified", "trend_established", "trend_confirmed"] as const satisfies ScreenStatus[];
export const STATUS_NAMES: Record<ScreenStatus, string> = {
  qualified: "Qualified",
  trend_established: "Trend established",
  trend_confirmed: "Trend confirmed",
};
export const RESULTS_PAGE = 50;

// The funnel stage of a screened stock (spec 08). Every stored row is qualified.
export const STAGES = ["momentum", "watching"] as const;
export type Stage = "qualified" | (typeof STAGES)[number];
export const STAGE_NAMES: Record<Stage, string> = { qualified: "Qualified", momentum: "Momentum", watching: "Watching" };
export function stageOf(r: { momentum: boolean; watching: boolean }): Stage {
  return r.watching ? "watching" : r.momentum ? "momentum" : "qualified";
}

const SORTS = {
  ticker: stockScreenResults.ticker,
  status: stockScreenResults.status,
  close: stockScreenResults.close,
  high: stockScreenResults.high52w,
  low: stockScreenResults.low52w,
  apr: stockScreenResults.apr52w,
  acc5: stockScreenResults.acc5,
  acc10: stockScreenResults.acc10,
  acc20: stockScreenResults.acc20,
  acc50: stockScreenResults.acc50,
  apr5: stockScreenResults.apr5,
  apr10: stockScreenResults.apr10,
  apr20: stockScreenResults.apr20,
  apr50: stockScreenResults.apr50,
} as const;
export type SortKey = keyof typeof SORTS;
export const SORT_KEYS = Object.keys(SORTS) as SortKey[];

const blank = z.literal("").transform(() => undefined);
export const ResultsQuery = z.object({
  session: z.iso.date().optional().or(blank),
  status: z.enum(STATUSES).optional().or(blank),
  stage: z.enum(STAGES).optional().or(blank),
  q: z.string().trim().max(20).optional().or(blank),
  sort: z.enum(SORT_KEYS as [SortKey, ...SortKey[]]).optional().or(blank),
  dir: z.enum(["asc", "desc"]).optional().or(blank),
  page: z.coerce.number().int().min(1).max(10_000).optional().or(blank),
});
export type ResultsQuery = z.infer<typeof ResultsQuery>;

/** Parse search params field by field; anything invalid falls back to its default. */
export function parseResultsQuery(params: Record<string, string | string[] | undefined>): ResultsQuery {
  const out: Record<string, unknown> = {};
  for (const [key, schema] of Object.entries(ResultsQuery.shape)) {
    const raw = params[key];
    const r = schema.safeParse(Array.isArray(raw) ? raw[0] : raw);
    if (r.success && r.data !== undefined) out[key] = r.data;
  }
  return out as ResultsQuery;
}

export function resultsHref(q: ResultsQuery, change: Partial<ResultsQuery> = {}): string {
  const merged = { ...q, ...change };
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(merged)) if (v !== undefined && !(k === "page" && v === 1)) p.set(k, String(v));
  const s = p.toString();
  return `/stocks${s ? `?${s}` : ""}`;
}

export async function sessions(limit = 60): Promise<string[]> {
  const rows = await db
    .selectDistinct({ d: stockScreenResults.sessionDate })
    .from(stockScreenResults)
    .orderBy(desc(stockScreenResults.sessionDate))
    .limit(limit);
  return rows.map((r) => r.d);
}

const n = (v: string | null) => (v === null ? null : Number(v));

export interface ResultRow {
  ticker: string;
  name: string | null;
  status: ScreenStatus;
  close: number;
  high_52w: number;
  low_52w: number;
  apr_52w: number;
  acc: Record<5 | 10 | 20 | 50, number | null>;
  apr: Record<5 | 10 | 20 | 50, number | null>;
  consistent: boolean;
  stage: Stage;
  evidence: DayEvidence | null;
}

export interface ResultsPage {
  session: string | null;
  rows: ResultRow[];
  total: number;
  page: number;
  pages: number;
  sort: SortKey;
  dir: "asc" | "desc";
}

export async function results(q: ResultsQuery): Promise<ResultsPage> {
  const session = q.session ?? (await sessions(1))[0] ?? null;
  const sort = q.sort ?? "apr20";
  const dir = q.dir ?? (sort === "ticker" ? "asc" : "desc");
  if (!session) return { session: null, rows: [], total: 0, page: 1, pages: 1, sort, dir };
  const where: SQL[] = [eq(stockScreenResults.sessionDate, session)];
  if (q.status) where.push(eq(stockScreenResults.status, q.status));
  if (q.stage === "watching") where.push(eq(stockScreenResults.watching, true));
  if (q.stage === "momentum") where.push(eq(stockScreenResults.momentum, true));
  if (q.q) {
    const term = q.q.replace(/[%_\\]/g, "");
    where.push(or(ilike(stockScreenResults.ticker, `${term}%`), ilike(stockTickers.name, `%${term}%`))!);
  }
  const cond = and(...where);
  const [{ total } = { total: 0 }] = await db
    .select({ total: count() })
    .from(stockScreenResults)
    .leftJoin(stockTickers, eq(stockTickers.ticker, stockScreenResults.ticker))
    .where(cond);
  const pages = Math.max(1, Math.ceil(total / RESULTS_PAGE));
  const page = Math.min(q.page ?? 1, pages);
  const col = SORTS[sort];
  const rows = await db
    .select({ r: stockScreenResults, name: stockTickers.name })
    .from(stockScreenResults)
    .leftJoin(stockTickers, eq(stockTickers.ticker, stockScreenResults.ticker))
    .where(cond)
    .orderBy(dir === "asc" ? dsql`${col} asc nulls last` : dsql`${col} desc nulls last`, asc(stockScreenResults.ticker))
    .limit(RESULTS_PAGE)
    .offset((page - 1) * RESULTS_PAGE);
  return { session, rows: rows.map(({ r, name }) => toRow(r, name)), total, page, pages, sort, dir };
}

function toRow(r: typeof stockScreenResults.$inferSelect, name: string | null): ResultRow {
  return {
    ticker: r.ticker,
    name,
    status: r.status,
    close: Number(r.close),
    high_52w: Number(r.high52w),
    low_52w: Number(r.low52w),
    apr_52w: Number(r.apr52w),
    acc: { 5: n(r.acc5), 10: n(r.acc10), 20: n(r.acc20), 50: n(r.acc50) },
    apr: { 5: n(r.apr5), 10: n(r.apr10), 20: n(r.apr20), 50: n(r.apr50) },
    consistent: r.consistent,
    stage: stageOf(r),
    evidence: r.indicators ?? null,
  };
}

export interface StockDetail {
  ticker: string;
  name: string | null;
  exchange: string | null;
  latest: (ResultRow & { session: string; closes: Record<0 | 5 | 10 | 20 | 50, number | null> }) | null;
  bars: { time: string; open: number; high: number; low: number; close: number }[];
  history: { session: string; status: ScreenStatus }[];
  stages: { session: string; stage: Stage }[];
  buys: StockBuy[];
  thresholds: { ratio: number | null; multiple: number | null; minApr: number | null };
}

const CHART_SESSIONS = 130; // about six months

export async function stockDetail(ticker: string): Promise<StockDetail | null> {
  const [info] = await db.select().from(stockTickers).where(eq(stockTickers.ticker, ticker)).limit(1);
  const [bars, history] = await Promise.all([
    db
      .select()
      .from(stockDailyBars)
      .where(eq(stockDailyBars.ticker, ticker))
      .orderBy(desc(stockDailyBars.sessionDate))
      .limit(CHART_SESSIONS),
    db
      .select()
      .from(stockScreenResults)
      .where(eq(stockScreenResults.ticker, ticker))
      .orderBy(desc(stockScreenResults.sessionDate))
      .limit(120),
  ]);
  if (!info && bars.length === 0 && history.length === 0) return null;
  const last = history[0];
  const thresholds = last ? await thresholdsAt(last.versionSet) : { ratio: null, multiple: null, minApr: null };
  // Status history: the sessions where the status changed, newest first.
  const changes: StockDetail["history"] = [];
  for (let i = history.length - 1; i >= 0; i--) {
    const h = history[i]!;
    if (changes.at(-1)?.status !== h.status) changes.push({ session: h.sessionDate, status: h.status });
  }
  const stages: StockDetail["stages"] = [];
  for (let i = history.length - 1; i >= 0; i--) {
    const stage = stageOf(history[i]!);
    if (stages.at(-1)?.stage !== stage) stages.push({ session: history[i]!.sessionDate, stage });
  }
  return {
    ticker,
    name: info?.name ?? null,
    exchange: info?.exchange ?? null,
    stages: stages.reverse(),
    buys: await stockBuys({ ticker }),
    latest: last
      ? {
          ...toRow(last, info?.name ?? null),
          session: last.sessionDate,
          closes: { 0: Number(last.close), 5: n(last.close5), 10: n(last.close10), 20: n(last.close20), 50: n(last.close50) },
        }
      : null,
    bars: bars
      .reverse()
      .map((b) => ({ time: b.sessionDate, open: Number(b.o), high: Number(b.h), low: Number(b.l), close: Number(b.c) })),
    history: changes.reverse(),
    thresholds,
  };
}

/** The qualification thresholds in force when the result was screened (its version set). */
async function thresholdsAt(versionSet: Record<string, number>) {
  const keys = ["stocks.rule1_near_high", "stocks.rule2_double", "stocks.rule3_apr"];
  const pairs = keys.filter((k) => versionSet[k] !== undefined).map((k) => and(eq(ruleVersions.key, k), eq(ruleVersions.version, versionSet[k]!)));
  const rows = pairs.length ? await db.select({ key: ruleVersions.key, params: ruleVersions.params }).from(ruleVersions).where(or(...pairs)) : [];
  const p = (k: string, name: string) => {
    const v = rows.find((r) => r.key === k)?.params[name];
    return typeof v === "number" ? v : v === undefined ? null : Number(v);
  };
  return { ratio: p(keys[0]!, "ratio"), multiple: p(keys[1]!, "multiple"), minApr: p(keys[2]!, "min_apr") };
}

export async function lastClose(ticker: string): Promise<{ close: number; session: string } | null> {
  const [b] = await db
    .select({ c: stockDailyBars.c, d: stockDailyBars.sessionDate })
    .from(stockDailyBars)
    .where(eq(stockDailyBars.ticker, ticker))
    .orderBy(desc(stockDailyBars.sessionDate))
    .limit(1);
  return b ? { close: Number(b.c), session: b.d } : null;
}

/** Sessions with a stored bar after the purchase date (as the worker counts them). */
export async function sessionsSince(ticker: string, purchaseDate: string): Promise<number> {
  const [r] = await db
    .select({ n: count() })
    .from(stockDailyBars)
    .where(and(eq(stockDailyBars.ticker, ticker), gt(stockDailyBars.sessionDate, purchaseDate)));
  return r?.n ?? 0;
}

// Buys and exits, written by the stock_eod job (spec 08).

export const EXIT_NAMES: Record<Exclude<StockSignalState, "open">, string> = {
  stopped: "Stop",
  trailing_stopped: "Trailing stop",
  sold: "Sell signal",
};

export interface StockBuy {
  id: string;
  ticker: string;
  buySession: string;
  entry: number;
  stopInitial: number;
  stopNow: number;
  trailingActive: boolean;
  highestClose: number;
  projection: number;
  projectionPct: number;
  horizonSessions: number;
  projectionSession: string | null;
  state: StockSignalState;
  exitSession: string | null;
  exitPrice: number | null;
  resultPct: number | null;
  lastClose: number | null;
  votes: Evidence;
  exitVotes: Evidence | null;
  hasProvisional: boolean;
  events: { session: string; kind: string; price: number | null }[];
}

/** Open buys first (newest first), then closed ones, newest exit first. */
export async function stockBuys(opts: { ticker?: string; closedLimit?: number } = {}): Promise<StockBuy[]> {
  const cond = opts.ticker ? eq(stockSignals.ticker, opts.ticker) : undefined;
  const [open, closed] = await Promise.all([
    db.select().from(stockSignals).where(and(eq(stockSignals.state, "open"), cond)).orderBy(desc(stockSignals.buySession)),
    db
      .select()
      .from(stockSignals)
      .where(and(ne(stockSignals.state, "open"), cond))
      .orderBy(desc(stockSignals.exitSession), desc(stockSignals.buySession))
      .limit(opts.closedLimit ?? 20),
  ]);
  const rows = [...open, ...closed];
  if (rows.length === 0) return [];
  const [events, closes] = await Promise.all([
    db
      .select()
      .from(stockSignalEvents)
      .where(inArray(stockSignalEvents.signalId, rows.map((r) => r.id)))
      .orderBy(asc(stockSignalEvents.id)),
    Promise.all(rows.map((r) => lastClose(r.ticker))),
  ]);
  return rows.map((r, i) => ({
    id: r.id,
    ticker: r.ticker,
    buySession: r.buySession,
    entry: Number(r.entry),
    stopInitial: Number(r.stopInitial),
    stopNow: Number(r.stopNow),
    trailingActive: r.trailingActive,
    highestClose: Number(r.highestClose),
    projection: Number(r.projection),
    projectionPct: Number(r.projectionPct),
    horizonSessions: r.horizonSessions,
    projectionSession: r.projectionSession,
    state: r.state,
    exitSession: r.exitSession,
    exitPrice: n(r.exitPrice),
    resultPct: n(r.resultPct),
    lastClose: closes[i]?.close ?? null,
    votes: r.votes,
    exitVotes: r.exitVotes,
    hasProvisional: r.hasProvisional,
    events: events.filter((e) => e.signalId === r.id).map((e) => ({ session: e.session, kind: e.kind, price: n(e.price) })),
  }));
}

export interface WatchRow {
  ticker: string;
  name: string | null;
  close: number;
  high_52w: number;
  apr10: number | null;
  votes: number;
  fired: string[];
}

/** The session's watch list, most buy votes first. */
export async function watchList(session: string | null): Promise<WatchRow[]> {
  if (!session) return [];
  const rows = await db
    .select({ r: stockScreenResults, name: stockTickers.name })
    .from(stockScreenResults)
    .leftJoin(stockTickers, eq(stockTickers.ticker, stockScreenResults.ticker))
    .where(and(eq(stockScreenResults.sessionDate, session), eq(stockScreenResults.watching, true)));
  return rows
    .map(({ r, name }) => {
      const fired = INDICATORS.filter((k) => r.indicators?.buy[k]?.fired);
      return { ticker: r.ticker, name, close: Number(r.close), high_52w: Number(r.high52w), apr10: n(r.apr10), votes: fired.length, fired };
    })
    .sort((a, b) => b.votes - a.votes || (b.apr10 ?? 0) - (a.apr10 ?? 0) || a.ticker.localeCompare(b.ticker));
}
