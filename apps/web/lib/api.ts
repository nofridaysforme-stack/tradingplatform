import "server-only";
import { eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { db } from "@/lib/db";
import { users } from "@/lib/db/schema";
import type { CurrentUser } from "@/lib/session";

/** Spec 14 error shape. */
export function apiError(status: number, code: string, message: string) {
  return NextResponse.json({ error: { code, message } }, { status, headers: { "Cache-Control": "no-store" } });
}

export function apiJson(body: unknown) {
  return NextResponse.json(body, { headers: { "Cache-Control": "no-store" } });
}

/** The signed-in, active user for an API route, or null (routes answer 401 instead of
 *  redirecting). */
export async function apiUser(): Promise<CurrentUser | null> {
  const session = await auth();
  const email = session?.user?.email;
  if (!email) return null;
  const [user] = await db.select().from(users).where(eq(users.email, email)).limit(1);
  return user && user.active ? user : null;
}

export const unauthorized = () => apiError(401, "unauthorized", "Sign in to continue.");

/** JSON POSTs from the portal itself only: same origin and a JSON body (with the Lax session
 *  cookie this blocks cross-site requests). */
export function sameOriginJson(request: Request): boolean {
  const origin = request.headers.get("origin");
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  const json = (request.headers.get("content-type") ?? "").startsWith("application/json");
  if (!json || !origin || !host) return false;
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}
