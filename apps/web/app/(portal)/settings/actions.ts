"use server";

import { eq } from "drizzle-orm";
import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { z } from "zod";
import { signOut } from "@/lib/auth";
import { db } from "@/lib/db";
import { users } from "@/lib/db/schema";
import { requireUser } from "@/lib/session";
import { parseTheme, THEME_COOKIE } from "@/lib/theme";

export async function setTheme(form: FormData): Promise<void> {
  await requireUser();
  const theme = parseTheme(String(form.get("theme")));
  (await cookies()).set(THEME_COOKIE, theme, {
    path: "/",
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    httpOnly: true,
    maxAge: 365 * 24 * 60 * 60,
  });
}

export async function signOutAction(): Promise<void> {
  await signOut({ redirectTo: "/sign-in" });
}

export interface ProfileState {
  ok?: boolean;
  message?: string;
  error?: string;
  fieldErrors?: Record<string, string>;
}

const ZONES = new Set(Intl.supportedValuesOf("timeZone"));

const Profile = z.object({
  name: z.string().trim().max(80, "Keep your name under 80 characters."),
  timezone: z.string().refine((v) => ZONES.has(v), "Choose a time zone from the list."),
});

/** Name and time zone. The time zone is used for quiet hours; prices and signals always show
 *  New York time (CLAUDE.md rule 5). */
export async function saveProfile(_: ProfileState, form: FormData): Promise<ProfileState> {
  const user = await requireUser();
  const r = Profile.safeParse({ name: form.get("name") ?? "", timezone: form.get("timezone") ?? "" });
  if (!r.success) {
    const fieldErrors: Record<string, string> = {};
    for (const i of r.error.issues) fieldErrors[String(i.path[0])] ??= i.message;
    return { error: "Check the highlighted fields.", fieldErrors };
  }
  await db.update(users).set({ name: r.data.name || null, timezone: r.data.timezone }).where(eq(users.id, user.id));
  revalidatePath("/settings");
  return { ok: true, message: "Profile saved" };
}
