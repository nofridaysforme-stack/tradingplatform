"use server";

import { and, eq, inArray } from "drizzle-orm";
import { revalidatePath } from "next/cache";
import { z } from "zod";
import { audit } from "@/lib/audit";
import { db } from "@/lib/db";
import { brokers, signalEvents, signals, users } from "@/lib/db/schema";
import { requireAdmin, requireUser } from "@/lib/session";

export interface ActionState {
  ok?: boolean;
  error?: string;
}

const Id = z.uuid();
const Reason = z.string().trim().min(1, "Write a reason first.").max(500, "Keep it under 500 characters.");
const Note = z.string().trim().min(1, "Write a note first.").max(500, "Keep it under 500 characters.");

/** Owners choose the broker whose spreads adjust their prices (spec 10). */
export async function setActiveBroker(_: ActionState, form: FormData): Promise<ActionState> {
  const user = await requireUser();
  const raw = form.get("brokerId");
  const brokerId = raw === "" ? null : Id.safeParse(raw).data;
  if (brokerId === undefined) return { error: "Choose a broker from the list." };
  if (brokerId) {
    const [b] = await db.select({ id: brokers.id }).from(brokers).where(and(eq(brokers.id, brokerId), eq(brokers.active, true)));
    if (!b) return { error: "That broker is no longer available." };
  }
  await db.update(users).set({ activeBrokerId: brokerId }).where(eq(users.id, user.id));
  revalidatePath("/", "layout");
  return { ok: true };
}

/** Admin: mark a live or closed signal invalid. Metrics exclude it (spec 10). */
export async function invalidateSignal(_: ActionState, form: FormData): Promise<ActionState> {
  const admin = await requireAdmin();
  const id = Id.safeParse(form.get("signalId"));
  const reason = Reason.safeParse(form.get("reason"));
  if (!id.success) return { error: "This signal doesn't exist." };
  if (!reason.success) return { error: reason.error.issues[0]?.message ?? "Write a reason first." };
  const done = await db.transaction(async (tx) => {
    const [before] = await tx
      .select({ state: signals.state })
      .from(signals)
      .where(and(eq(signals.id, id.data), inArray(signals.state, ["open", "confirmed", "target_hit", "stop_hit", "expired", "ambiguous"])))
      .for("update");
    if (!before) return false;
    const now = new Date();
    await tx.update(signals).set({ state: "invalidated", closedAt: now }).where(eq(signals.id, id.data));
    await tx.insert(signalEvents).values({ signalId: id.data, at: now, kind: "invalidated", note: reason.data });
    await audit(tx, {
      userId: admin.id,
      action: "signal.invalidate",
      target: id.data,
      before,
      after: { state: "invalidated", reason: reason.data },
    });
    return true;
  });
  if (!done) return { error: "This signal is already invalid." };
  revalidatePath(`/signals/${id.data}`);
  return { ok: true };
}

/** Admin: add a note to a signal's timeline. */
export async function addSignalNote(_: ActionState, form: FormData): Promise<ActionState> {
  const admin = await requireAdmin();
  const id = Id.safeParse(form.get("signalId"));
  const note = Note.safeParse(form.get("note"));
  if (!id.success) return { error: "This signal doesn't exist." };
  if (!note.success) return { error: note.error.issues[0]?.message ?? "Write a note first." };
  const [exists] = await db.select({ id: signals.id }).from(signals).where(eq(signals.id, id.data));
  if (!exists) return { error: "This signal doesn't exist." };
  await db.transaction(async (tx) => {
    await tx.insert(signalEvents).values({ signalId: id.data, kind: "note", note: note.data });
    await audit(tx, { userId: admin.id, action: "signal.note", target: id.data, after: { note: note.data } });
  });
  revalidatePath(`/signals/${id.data}`);
  return { ok: true };
}
