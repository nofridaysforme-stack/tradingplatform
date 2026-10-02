// The dashboard status line and health dot, from what the worker reports with its heartbeat.
// The portal does not decide market hours or the trading window itself.
import type { WorkerMarket } from "@/lib/db/schema";
import { nyDayTime, nyTime } from "@/lib/format";

export const HEARTBEAT_STALE_MS = 5 * 60_000; // spec 14, /api/health

export type Health = "ok" | "warn" | "down";

export interface MarketView {
  health: Health;
  line: string;
  stale: string[];
}

export function marketView(heartbeatAt: Date | null, market: WorkerMarket | null, now: Date): MarketView {
  const clock = `${nyTime(now)} NY`;
  if (!heartbeatAt || !market || now.getTime() - heartbeatAt.getTime() > HEARTBEAT_STALE_MS) {
    return { health: "down", line: `Market status unknown. The scanner hasn't reported recently · ${clock}`, stale: [] };
  }
  if (!market.forex_open) {
    const opens = market.next_open ? ` · Opens ${nyDayTime(new Date(market.next_open))} NY` : "";
    return { health: "ok", line: `Forex closed${opens} · ${clock}`, stale: [] };
  }
  const parts = ["Forex open", windowText(market), clock];
  return { health: market.stale.length ? "warn" : "ok", line: parts.join(" · "), stale: market.stale };
}

function windowText(m: WorkerMarket): string {
  if (!m.window_enabled) return "3/8 window off";
  if (!m.in_window) return "Outside 3/8 window";
  // With both windows the later end is shown; they overlap in the seeded hours.
  const end = m.windows.map((w) => w.end).sort().at(-1);
  return `In 3/8 window until ${end}`;
}

export function staleBanner(symbol: string): string {
  return `Prices for ${symbol} haven't updated for 30 minutes. Alerts for this pair are paused until data resumes.`;
}
