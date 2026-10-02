"use server";

import { eq } from "drizzle-orm";
import { revalidatePath } from "next/cache";
import { z } from "zod";
import { audit } from "@/lib/audit";
import { db } from "@/lib/db";
import { econEvents } from "@/lib/db/schema";
import { nyLocalToUtc } from "@/lib/ny-time";
import { requireAdmin } from "@/lib/session";

export interface EconState {
  ok?: boolean;
  message?: string;
  error?: string;
  fieldErrors?: Record<string, string>;
}

const Event = z.object({
  at: z.string().transform((v, ctx) => {
    const d = nyLocalToUtc(v);
    if (!d) ctx.addIssue({ code: "custom", message: "Enter a date and time in New York time." });
    return d ?? new Date(0);
  }),
  currency: z
    .string()
    .trim()
    .toUpperCase()
    .regex(/^[A-Z]{3}$/, "Use a three-letter currency code, for example USD."),
  title: z.string().trim().min(1, "Enter the event name.").max(200, "Keep the name under 200 characters."),
  impact: z.enum(["high", "medium", "low"], "Choose the impact."),
});

/** Admins add events by hand until an automatic calendar is chosen (spec 20, T1). */
export async function createEconEvent(_: EconState, form: FormData): Promise<EconState> {
  const admin = await requireAdmin();
  const r = Event.safeParse({
    at: form.get("at") ?? "",
    currency: form.get("currency") ?? "",
    title: form.get("title") ?? "",
    impact: form.get("impact") ?? "",
  });
  if (!r.success) {
    const fieldErrors: Record<string, string> = {};
    for (const i of r.error.issues) fieldErrors[String(i.path[0])] ??= i.message;
    return { error: "Check the highlighted fields.", fieldErrors };
  }
  await db.transaction(async (tx) => {
    const [row] = await tx
      .insert(econEvents)
      .values({ ...r.data, createdBy: admin.id })
      .returning({ id: econEvents.id });
    await audit(tx, { userId: admin.id, action: "econ.create", target: row!.id, after: { ...r.data, at: r.data.at.toISOString() } });
  });
  revalidatePath("/econ");
  return { ok: true, message: "Event added" };
}

export async function deleteEconEvent(_: EconState, form: FormData): Promise<EconState> {
  const admin = await requireAdmin();
  const id = z.uuid().safeParse(form.get("id"));
  if (!id.success) return { error: "This event doesn't exist." };
  const removed = await db.transaction(async (tx) => {
    const [gone] = await tx.delete(econEvents).where(eq(econEvents.id, id.data)).returning();
    if (gone) {
      await audit(tx, {
        userId: admin.id,
        action: "econ.delete",
        target: gone.id,
        before: { at: gone.at.toISOString(), currency: gone.currency, title: gone.title, impact: gone.impact },
      });
    }
    return gone;
  });
  if (!removed) return { error: "This event was already deleted." };
  revalidatePath("/econ");
  return { ok: true, message: "Event deleted" };
}
