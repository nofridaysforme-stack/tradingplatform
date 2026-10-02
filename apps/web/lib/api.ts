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
