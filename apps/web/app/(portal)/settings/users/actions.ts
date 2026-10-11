"use server";

import { and, count, eq, sql } from "drizzle-orm";
import { revalidatePath } from "next/cache";
import { z } from "zod";
import { mayAccess, normalizeEmail } from "@/lib/access";
import { audit } from "@/lib/audit";
import { signIn } from "@/lib/auth";
import { db } from "@/lib/db";
import { allowlist, sessions, users, verificationTokens } from "@/lib/db/schema";
import { linkCapture } from "@/lib/mail";
import { requireAdmin } from "@/lib/session";

export interface UserState {
  ok?: boolean;
  message?: string;
  error?: string;
  fieldErrors?: Record<string, string>;
  link?: string;
}

/** How long a link made for an admin to hand over stays usable. It still works only once. */
const HANDOVER_HOURS = 24;

const done = (message: string): UserState => {
  revalidatePath("/settings/users");
  return { ok: true, message };
};

/** Spec 15: access is allowlist only. */
export async function addAllowlistEmail(_: UserState, form: FormData): Promise<UserState> {
  const admin = await requireAdmin();
  const email = z.email("Enter an email address.").safeParse(normalizeEmail(String(form.get("email") ?? "")));
  if (!email.success) return { error: "Check the highlighted fields.", fieldErrors: { email: "Enter an email address." } };
  const added = await db.transaction(async (tx) => {
    const rows = await tx.insert(allowlist).values({ email: email.data, addedBy: admin.id }).onConflictDoNothing().returning();
    if (rows.length) await audit(tx, { userId: admin.id, action: "allowlist.add", target: email.data });
    return rows.length > 0;
  });
  if (!added) return { error: "Check the highlighted fields.", fieldErrors: { email: "That email is already approved." } };
  return done(`${email.data} can now sign in`);
}

/** Removing an email blocks new sign-in links. People who already signed in are deactivated
 *  instead, so their history stays attached. */
export async function removeAllowlistEmail(_: UserState, form: FormData): Promise<UserState> {
  const admin = await requireAdmin();
  const email = normalizeEmail(String(form.get("email") ?? ""));
  const [user] = await db.select({ id: users.id }).from(users).where(eq(users.email, email));
  if (user) return { error: "This person has signed in. Deactivate them instead." };
  const removed = await db.transaction(async (tx) => {
    const rows = await tx.delete(allowlist).where(eq(allowlist.email, email)).returning();
    if (rows.length) await audit(tx, { userId: admin.id, action: "allowlist.remove", target: email });
    return rows.length > 0;
  });
  return removed ? done(`${email} removed`) : { error: "That email isn't on the list." };
}

export async function setUserRole(_: UserState, form: FormData): Promise<UserState> {
  const admin = await requireAdmin();
  const id = z.uuid().safeParse(form.get("id"));
  const role = z.enum(["owner", "admin"]).safeParse(form.get("role"));
  if (!id.success || !role.success) return { error: "Choose a role." };
  const result = await db.transaction(async (tx) => {
    const [target] = await tx.select().from(users).where(eq(users.id, id.data)).for("update");
    if (!target) return "missing";
    if (target.role === role.data) return "same";
    if (target.role === "admin" && role.data === "owner") {
      const [{ n } = { n: 0 }] = await tx
        .select({ n: count() })
        .from(users)
        .where(and(eq(users.role, "admin"), eq(users.active, true)));
      if (n <= 1) return "last";
    }
    await tx.update(users).set({ role: role.data }).where(eq(users.id, id.data));
    await audit(tx, { userId: admin.id, action: "user.role", target: target.email, before: { role: target.role }, after: { role: role.data } });
    return target.email;
  });
  if (result === "missing") return { error: "This user doesn't exist." };
  if (result === "same") return { error: "That is already their role." };
  if (result === "last") return { error: "Keep at least one active admin." };
  return done(`${result} is now ${role.data === "admin" ? "an admin" : "an owner"}`);
}

/** Deactivating signs the person out everywhere at once (their sessions are deleted). */
export async function setUserActive(_: UserState, form: FormData): Promise<UserState> {
  const admin = await requireAdmin();
  const id = z.uuid().safeParse(form.get("id"));
  if (!id.success) return { error: "This user doesn't exist." };
  const active = form.get("active") === "true";
  if (!active && id.data === admin.id) return { error: "You can't deactivate yourself." };
  const result = await db.transaction(async (tx) => {
    const [target] = await tx.select().from(users).where(eq(users.id, id.data)).for("update");
    if (!target) return "missing";
    if (!active && target.role === "admin") {
      const [{ n } = { n: 0 }] = await tx
        .select({ n: count() })
        .from(users)
        .where(and(eq(users.role, "admin"), eq(users.active, true)));
      if (n <= 1) return "last";
    }
    await tx.update(users).set({ active }).where(eq(users.id, id.data));
    if (!active) await tx.delete(sessions).where(eq(sessions.userId, id.data));
    await audit(tx, { userId: admin.id, action: active ? "user.reactivate" : "user.deactivate", target: target.email });
    return target.email;
  });
  if (result === "missing") return { error: "This user doesn't exist." };
  if (result === "last") return { error: "Keep at least one active admin." };
  return done(active ? `${result} can sign in again` : `${result} is deactivated and signed out`);
}

/** A sign-in link the admin sends themselves (text message, chat), for when email can't reach
 *  the person yet. The same single-use link as the email one, for approved emails only. */
export async function createSignInLink(_: UserState, form: FormData): Promise<UserState> {
  const admin = await requireAdmin();
  const email = normalizeEmail(String(form.get("email") ?? ""));
  if (!(await mayAccess(email))) return { error: "That email isn't approved, or the person is deactivated." };
  const capture: { url?: string } = {};
  try {
    await linkCapture.run(capture, () => signIn("email", { email, redirect: false, redirectTo: "/dashboard" }));
  } catch {
    return { error: "The link couldn't be made. Try again." };
  }
  if (!capture.url) return { error: "The link couldn't be made. Try again." };
  await db.transaction(async (tx) => {
    // The newest link gets a day instead of 15 minutes, since it travels by hand.
    await tx
      .update(verificationTokens)
      .set({ expires: sql`now() + make_interval(hours => ${HANDOVER_HOURS})` })
      .where(
        and(
          eq(verificationTokens.identifier, email),
          sql`${verificationTokens.expires} = (select max(expires) from verification_tokens where identifier = ${email})`,
        ),
      );
    // The link itself is never stored in the audit log or logged (spec 15).
    await audit(tx, { userId: admin.id, action: "allowlist.sign_in_link", target: email });
  });
  return { ok: true, message: `Link for ${email}`, link: capture.url };
}
