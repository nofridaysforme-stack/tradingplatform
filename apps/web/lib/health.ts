import "server-only";
import { and, asc, desc, eq, gte, inArray, sql as dsql } from "drizzle-orm";
import { db } from "@/lib/db";
import { instruments, jobRuns, workerHeartbeat, type WorkerMarket } from "@/lib/db/schema";

const DAY_MS = 86_400_000;

export interface JobView {
  id: number;
  job: string;
  startedAt: string;
  finishedAt: string | null;
  ok: boolean | null;
  detail: Record<string, unknown> | null;
}

export interface HealthDetail {
  heartbeat: { at: string; version: string | null } | null;
  market: WorkerMarket | null;
  pairs: { symbol: string; lastBar: string | null; stale: boolean }[];
  latest: Record<"forex_bar_close" | "forex_day_roll" | "stock_eod" | "backfill", JobView | null>;
  runs: JobView[];
  deliveries: { channel: string; status: string; n: number }[];
}

const toJob = (r: typeof jobRuns.$inferSelect): JobView => ({
  id: r.id,
  job: r.job,
  startedAt: r.startedAt.toISOString(),
  finishedAt: r.finishedAt?.toISOString() ?? null,
  ok: r.ok,
  detail: r.detail,
});

export async function healthDetail(now: Date): Promise<HealthDetail> {
  const [hb] = await db.select().from(workerHeartbeat).limit(1);
  const stale = new Set(hb?.market?.forex_open ? hb.market.stale : []);
  const [pairs, runs, deliveries, ...latest] = await Promise.all([
    db
      .select({
        symbol: instruments.symbol,
        lastBar: dsql<Date | null>`(select max(c.ts) from candles c where c.instrument_id = ${instruments.id} and c.granularity = 'M15')`,
      })
      .from(instruments)
      .where(eq(instruments.enabled, true))
      .orderBy(asc(instruments.sortOrder), asc(instruments.symbol)),
    db.select().from(jobRuns).where(gte(jobRuns.startedAt, new Date(now.getTime() - DAY_MS))).orderBy(desc(jobRuns.startedAt)).limit(50),
    db.execute<{ channel: string; status: string; n: number }>(
      dsql`select channel::text, status::text, count(*)::int as n from notifications where created_at >= ${new Date(now.getTime() - DAY_MS).toISOString()} group by 1, 2 order by 1, 2`,
    ),
    ...(["forex_bar_close", "forex_day_roll", "stock_eod", "backfill"] as const).map((job) =>
      db.select().from(jobRuns).where(and(eq(jobRuns.job, job), inArray(jobRuns.ok, [true, false]))).orderBy(desc(jobRuns.startedAt)).limit(1),
    ),
  ]);
  const [bar, roll, stock, backfill] = latest.map((rows) => (rows[0] ? toJob(rows[0]) : null));
  return {
    heartbeat: hb ? { at: hb.at.toISOString(), version: hb.version } : null,
    market: hb?.market ?? null,
    pairs: pairs.map((p) => ({
      symbol: p.symbol,
      lastBar: p.lastBar ? new Date(p.lastBar).toISOString() : null,
      stale: stale.has(p.symbol),
    })),
    latest: { forex_bar_close: bar ?? null, forex_day_roll: roll ?? null, stock_eod: stock ?? null, backfill: backfill ?? null },
    runs: runs.map(toJob),
    deliveries: [...deliveries],
  };
}
