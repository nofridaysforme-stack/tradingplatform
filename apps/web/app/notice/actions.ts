"use server";

import { eq } from "drizzle-orm";
import { redirect } from "next/navigation";
import { db } from "@/lib/db";
import { users } from "@/lib/db/schema";
import { requireUser } from "@/lib/session";

export async function acknowledgeNotice(): Promise<void> {
  const user = await requireUser();
  if (!user.acknowledgedNoticeAt) {
    await db.update(users).set({ acknowledgedNoticeAt: new Date() }).where(eq(users.id, user.id));
  }
  redirect("/dashboard");
}
