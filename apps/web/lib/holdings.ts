import "server-only";
import { and, desc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { holdings, ruleDefinitions, ruleVersions } from "@/lib/db/schema";
import { checkHolding, salesTarget, type HoldingCheck, type SalesTarget } from "@/lib/holdings-math";
import { lastClose, sessionsSince } from "@/lib/stocks";

export interface HoldingView {
  id: string;
  ticker: string;
  purchasePrice: number;
  purchaseDate: string;
  expectedProfitPct: number;
  horizonSessions: number;
  closed: boolean;
  notes: string | null;
  plan: SalesTarget;
  lastClose: number | null;
  lastSession: string | null;
  check: HoldingCheck | null;
  /** Written by the scanner after each session (spec 08); null until its first run. */
  track: {
    session: string;
    stopNow: number | null;
    trailingActive: boolean;
    highestClose: number | null;
    sell: { reason: "stopped" | "trailing_stopped" | "sold"; session: string | null; price: number | null } | null;
  } | null;
}

/** The caller's own holdings, newest first, with targets and progress. */
export async function listHoldings(userId: string): Promise<HoldingView[]> {
  const rows = await db.select().from(holdings).where(eq(holdings.userId, userId)).orderBy(desc(holdings.purchaseDate), desc(holdings.createdAt));
  return Promise.all(
    rows.map(async (h) => {
      const price = Number(h.purchasePrice);
      const pct = Number(h.expectedProfitPct);
      const [last, elapsed] = await Promise.all([lastClose(h.ticker), sessionsSince(h.ticker, h.purchaseDate)]);
      return {
        id: h.id,
        ticker: h.ticker,
        purchasePrice: price,
        purchaseDate: h.purchaseDate,
        expectedProfitPct: pct,
        horizonSessions: h.horizonSessions,
        closed: h.closed,
        notes: h.notes,
        plan: salesTarget(price, pct, h.horizonSessions),
        lastClose: last?.close ?? null,
        lastSession: last?.session ?? null,
        check: last ? checkHolding(price, pct, h.horizonSessions, last.close, elapsed) : null,
        track: h.trackedSession
          ? {
              session: h.trackedSession,
              stopNow: h.stopNow === null ? null : Number(h.stopNow),
              trailingActive: h.trailingActive,
              highestClose: h.highestClose === null ? null : Number(h.highestClose),
              sell: h.sellReason
                ? { reason: h.sellReason, session: h.sellSession, price: h.sellPrice === null ? null : Number(h.sellPrice) }
                : null,
            }
          : null,
      };
    }),
  );
}

/** New holdings start from the stocks.momentum rule's projection (spec 08: 35 percent in 20 sessions). */
export async function holdingDefaults(): Promise<{ expectedProfitPct: number; horizonSessions: number }> {
  const [r] = await db
    .select({ params: ruleVersions.params })
    .from(ruleVersions)
    .innerJoin(ruleDefinitions, and(eq(ruleDefinitions.key, ruleVersions.key), eq(ruleDefinitions.currentVersion, ruleVersions.version)))
    .where(eq(ruleVersions.key, "stocks.momentum"))
    .limit(1);
  const pct = Number(r?.params.projection_pct);
  const horizon = Number(r?.params.horizon_sessions);
  return {
    expectedProfitPct: Number.isFinite(pct) && pct > 0 ? pct : 35,
    horizonSessions: Number.isInteger(horizon) && horizon > 0 ? horizon : 20,
  };
}
