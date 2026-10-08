import { apiJson, apiUser, unauthorized } from "@/lib/api";
import { forexEnabled } from "@/lib/app-settings";
import { nyTime } from "@/lib/format";
import { marketView } from "@/lib/market";
import { heartbeat } from "@/lib/signals";

export async function GET() {
  if (!(await apiUser())) return unauthorized();
  const now = new Date();
  const [hb, forex] = await Promise.all([heartbeat(), forexEnabled()]);
  const view = marketView(hb?.at ?? null, hb?.market ?? null, now, forex);
  const m = hb?.market;
  return apiJson({
    ...view,
    new_york_time: nyTime(now),
    heartbeat_at: hb?.at.toISOString() ?? null,
    forex_open: view.health === "down" ? null : (m?.forex_open ?? null),
    in_window: view.health === "down" ? null : (m?.in_window ?? null),
    trading_day: m?.trading_day ?? null,
  });
}
