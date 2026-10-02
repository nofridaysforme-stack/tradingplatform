import "server-only";
import { eq } from "drizzle-orm";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { db } from "@/lib/db";
import { users } from "@/lib/db/schema";

export type CurrentUser = typeof users.$inferSelect;

/** The signed-in, active user, or a redirect to sign in. Every page and action checks this
 *  (spec 15: session, active flag, and role on every request). */
export async function requireUser(): Promise<CurrentUser> {
  const session = await auth();
  const email = session?.user?.email;
  if (!email) redirect("/sign-in");
  const [user] = await db.select().from(users).where(eq(users.email, email)).limit(1);
  if (!user || !user.active) redirect("/sign-in?error=inactive");
  return user;
}

export async function requireAdmin(): Promise<CurrentUser> {
  const user = await requireUser();
  if (user.role !== "admin") redirect("/dashboard");
  return user;
}
