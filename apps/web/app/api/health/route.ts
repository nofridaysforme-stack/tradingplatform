import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { appSettings, workerHeartbeat } from "@/lib/db/schema";
import { healthReasons } from "@/lib/health-status";

// Public and minimal (spec 14): an uptime monitor polls it. No signal or price data.
export const dynamic = "force-dynamic";

export async function GET() {
  let dbOk = true;
  let hb: typeof workerHeartbeat.$inferSelect | undefined;
  let settings: { forexEnabled: boolean } | undefined;
  try {
    [hb] = await db.select().from(workerHeartbeat).limit(1);
    [settings] = await db.select({ forexEnabled: appSettings.forexEnabled }).from(appSettings);
  } catch {
    dbOk = false;
  }
  const reasons = healthReasons({ dbOk, heartbeatAt: hb?.at ?? null, market: hb?.market ?? null, now: new Date(), forex: settings?.forexEnabled ?? true });
  const headers = { "Cache-Control": "no-store" };
  return reasons.length
    ? NextResponse.json({ ok: false, reasons }, { status: 503, headers })
    : NextResponse.json({ ok: true }, { headers });
}
