import "server-only";
import { and, asc, gte, lte } from "drizzle-orm";
import { db } from "@/lib/db";
import { econEvents } from "@/lib/db/schema";

const DAY = 86_400_000;

export interface EconEvent {
  id: string;
  at: string;
  currency: string;
  title: string;
  impact: "high" | "medium" | "low";
}

/** Events from a week ago to a month ahead. The worker reads them for the econ window rule. */
export async function econWindow(now: Date): Promise<{ upcoming: EconEvent[]; recent: EconEvent[] }> {
  const rows = await db
    .select()
    .from(econEvents)
    .where(and(gte(econEvents.at, new Date(now.getTime() - 7 * DAY)), lte(econEvents.at, new Date(now.getTime() + 31 * DAY))))
    .orderBy(asc(econEvents.at));
  const all = rows.map((r) => ({ id: r.id, at: r.at.toISOString(), currency: r.currency.trim(), title: r.title, impact: r.impact }));
  return {
    upcoming: all.filter((e) => new Date(e.at) >= now),
    recent: all.filter((e) => new Date(e.at) < now).reverse(),
  };
}
