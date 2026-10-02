import "server-only";
import { and, asc, desc, eq, max } from "drizzle-orm";
import { db } from "@/lib/db";
import { candles, instruments, levels } from "@/lib/db/schema";

// Reads the level sets the worker computes at each day roll (spec 07, spec 09 levels table).

export interface Pair {
  id: string;
  symbol: string;
  decimals: number;
}

export const PIVOT_KEYS = ["R3", "R2", "R1", "P", "S1", "S2", "S3"] as const;
export const LADDER_STEPS = [
  ["reset", "Reset"],
  ["take_profit", "Take profit"],
  ["confirmation", "Confirmation"],
  ["break", "Break"],
] as const;

export type Pivots = Partial<Record<(typeof PIVOT_KEYS)[number], number>>;

export interface Ladder {
  pivot: number;
  fib: number | null;
  range: number | null;
  up: Partial<Record<(typeof LADDER_STEPS)[number][0], number>>;
  down: Partial<Record<(typeof LADDER_STEPS)[number][0], number>>;
}

export interface PairLevels {
  instrument: string;
  decimals: number;
  trading_day: string | null;
  daily: Pivots | null;
  weekly: Pivots | null;
  monthly: Pivots | null;
  prev_day: { PDH?: number; PDL?: number } | null;
  fib_pivot: Ladder | null;
  last_price: number | null;
  last_price_at: string | null;
}

export async function listPairs(): Promise<Pair[]> {
  return db
    .select({ id: instruments.id, symbol: instruments.symbol, decimals: instruments.displayDecimals })
    .from(instruments)
    .where(eq(instruments.enabled, true))
    .orderBy(asc(instruments.sortOrder), asc(instruments.symbol));
}

const num = (v: unknown): number | undefined => {
  const n = typeof v === "number" || typeof v === "string" ? Number(v) : NaN;
  return Number.isFinite(n) ? n : undefined;
};

function pick<K extends string>(data: Record<string, unknown>, keys: readonly K[]): Partial<Record<K, number>> {
  const out: Partial<Record<K, number>> = {};
  for (const k of keys) {
    const v = num(data[k]);
    if (v !== undefined) out[k] = v;
  }
  return out;
}

function ladder(data: Record<string, unknown>): Ladder | null {
  const pivot = num(data.pivot);
  if (pivot === undefined) return null;
  const steps = LADDER_STEPS.map(([k]) => k);
  return {
    pivot,
    fib: num(data.fib) ?? null,
    range: num(data.range_units) ?? null,
    up: pick((data.up ?? {}) as Record<string, unknown>, steps),
    down: pick((data.down ?? {}) as Record<string, unknown>, steps),
  };
}

/** Level sets for one pair on a trading day (the latest computed day when none is given). */
export async function pairLevels(pair: Pair, day?: string): Promise<PairLevels> {
  let tradingDay = day ?? null;
  if (!tradingDay) {
    const [row] = await db
      .select({ day: max(levels.tradingDay) })
      .from(levels)
      .where(eq(levels.instrumentId, pair.id));
    tradingDay = row?.day ?? null;
  }
  const [sets, last] = await Promise.all([
    tradingDay
      ? db
          .select({ kind: levels.setKind, data: levels.data })
          .from(levels)
          .where(and(eq(levels.instrumentId, pair.id), eq(levels.tradingDay, tradingDay)))
      : Promise.resolve([]),
    db
      .select({ ts: candles.ts, c: candles.c })
      .from(candles)
      .where(and(eq(candles.instrumentId, pair.id), eq(candles.granularity, "M15")))
      .orderBy(desc(candles.ts))
      .limit(1),
  ]);
  const byKind = new Map(sets.map((s) => [s.kind, s.data]));
  const pivots = (k: "daily" | "weekly" | "monthly") => {
    const d = byKind.get(k);
    return d ? pick(d, PIVOT_KEYS) : null;
  };
  const prev = byKind.get("prev_day");
  const fib = byKind.get("fib_pivot");
  return {
    instrument: pair.symbol,
    decimals: pair.decimals,
    trading_day: tradingDay,
    daily: pivots("daily"),
    weekly: pivots("weekly"),
    monthly: pivots("monthly"),
    prev_day: prev ? pick(prev, ["PDH", "PDL"] as const) : null,
    fib_pivot: fib ? ladder(fib) : null,
    last_price: last[0] ? Number(last[0].c) : null,
    last_price_at: last[0] ? last[0].ts.toISOString() : null,
  };
}
