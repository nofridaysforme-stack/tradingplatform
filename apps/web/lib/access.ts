import "server-only";
import { and, eq, gt, sql as dsql } from "drizzle-orm";
import { db } from "@/lib/db";
import { allowlist, users, verificationTokens } from "@/lib/db/schema";

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

/** An email may sign in when it is on the allowlist and its user (if any) is active. */
export async function mayAccess(email: string): Promise<boolean> {
  const normalized = normalizeEmail(email);
  const [listed] = await db.select().from(allowlist).where(eq(allowlist.email, normalized)).limit(1);
  if (!listed) return false;
  const [user] = await db.select({ active: users.active }).from(users).where(eq(users.email, normalized)).limit(1);
  return !user || user.active;
}

// Spec 15: 5 sign-in requests per email per 15 minutes, 20 per IP per hour.
export const EMAIL_LIMIT = 5;
export const IP_LIMIT = 20;
const IP_WINDOW_MS = 60 * 60 * 1000;

/** Sign-in links are valid for 15 minutes, so unexpired tokens are the ones issued in the
 *  last 15 minutes. Counting them needs no extra table and survives restarts. */
export async function emailRequestsInWindow(email: string): Promise<number> {
  const [row] = await db
    .select({ n: dsql<number>`count(*)::int` })
    .from(verificationTokens)
    .where(and(eq(verificationTokens.identifier, normalizeEmail(email)), gt(verificationTokens.expires, new Date())));
  return row?.n ?? 0;
}

/** Per-IP limit, kept in memory: the web service runs as one instance. */
export class IpLimiter {
  private hits = new Map<string, number[]>();
  constructor(
    private readonly limit = IP_LIMIT,
    private readonly windowMs = IP_WINDOW_MS,
  ) {}
  allow(ip: string, now = Date.now()): boolean {
    const recent = (this.hits.get(ip) ?? []).filter((t) => now - t < this.windowMs);
    if (recent.length >= this.limit) {
      this.hits.set(ip, recent);
      return false;
    }
    recent.push(now);
    this.hits.set(ip, recent);
    return true;
  }
}

export const ipLimiter = new IpLimiter();
