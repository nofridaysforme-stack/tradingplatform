import type { WorkerMarket } from "@/lib/db/schema";
import { HEARTBEAT_STALE_MS } from "@/lib/market";

export type HealthReason = "database_unreachable" | "heartbeat_stale" | "pairs_stale";

/** Spec 14 /api/health: healthy when the database answers, the heartbeat is under 5 minutes
 *  old, and no enabled pair is stale while forex is open. */
export function healthReasons(input: {
  dbOk: boolean;
  heartbeatAt: Date | null;
  market: WorkerMarket | null;
  now: Date;
}): HealthReason[] {
  if (!input.dbOk) return ["database_unreachable"];
  const reasons: HealthReason[] = [];
  if (!input.heartbeatAt || input.now.getTime() - input.heartbeatAt.getTime() > HEARTBEAT_STALE_MS) reasons.push("heartbeat_stale");
  if (input.market?.forex_open && input.market.stale.length > 0) reasons.push("pairs_stale");
  return reasons;
}
