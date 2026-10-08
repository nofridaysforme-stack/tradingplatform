"use server";

import { eq } from "drizzle-orm";
import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { z } from "zod";
import { audit } from "@/lib/audit";
import { signOut } from "@/lib/auth";
import { db } from "@/lib/db";
import { appSettings, users } from "@/lib/db/schema";
import { requireAdmin, requireUser } from "@/lib/session";
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

export interface ForexState {
  ok?: boolean;
  message?: string;
  error?: string;
}

/** Pauses or resumes the whole forex side (decision 2026-10-08). Nothing is deleted. */
export async function setForex(_: ForexState, form: FormData): Promise<ForexState> {
  const admin = await requireAdmin();
  const choice = z.enum(["pause", "resume"]).safeParse(form.get("forex"));
  if (!choice.success) return { error: "Choose to pause or resume forex." };
  const enabled = choice.data === "resume";
  await db.transaction(async (tx) => {
    const [before] = await tx.select({ forexEnabled: appSettings.forexEnabled }).from(appSettings);
    await tx.update(appSettings).set({ forexEnabled: enabled, updatedBy: admin.id, updatedAt: new Date() });
    await audit(tx, {
      userId: admin.id,
      action: "settings.forex",
      target: "forex",
      before: before ? { forex_enabled: before.forexEnabled } : null,
      after: { forex_enabled: enabled },
    });
  });
  revalidatePath("/", "layout");
  return { ok: true, message: enabled ? "Forex resumed" : "Forex paused" };
}
