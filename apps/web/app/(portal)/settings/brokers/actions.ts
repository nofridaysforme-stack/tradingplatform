"use server";

import { and, eq, inArray, ne } from "drizzle-orm";
import { revalidatePath } from "next/cache";
import { z } from "zod";
import { audit } from "@/lib/audit";
import { db } from "@/lib/db";
import { brokerSpreads, brokers, instruments } from "@/lib/db/schema";
import { requireAdmin } from "@/lib/session";

export interface BrokerState {
  ok?: boolean;
  message?: string;
  error?: string;
  fieldErrors?: Record<string, string>;
}

const Broker = z.object({
  name: z.string().trim().min(1, "Enter the broker's name.").max(60, "Keep the name under 60 characters."),
  template: z
    .string()
    .trim()
    .max(500, "Keep the link under 500 characters.")
    .refine((v) => v === "" || (/^https:\/\/[^\s]+$/.test(v) && v.includes("{symbol}")), "Use an https link that contains {symbol}."),
  notes: z.string().trim().max(500, "Keep notes under 500 characters."),
});
const Spread = z.coerce.number({ error: "Enter a number of pips." }).min(0, "Use 0 or more.").max(50, "Use 50 or less.");
const Override = z.string().trim().max(30, "Keep the symbol under 30 characters.").regex(/^[A-Za-z0-9._\-/]*$/, "Use letters, numbers, dots, dashes, or slashes.");

/** Create or edit a broker with its typical spread per pair (spec 10, spec 14 upsertBroker,
 *  upsertBrokerSpreads). Leaving a pair's spread blank removes it. */
export async function saveBroker(_: BrokerState, form: FormData): Promise<BrokerState> {
  const admin = await requireAdmin();
  const idRaw = form.get("id");
  const id = idRaw ? z.uuid().safeParse(idRaw).data : null;
  if (idRaw && !id) return { error: "This broker doesn't exist." };
  const fieldErrors: Record<string, string> = {};
  const b = Broker.safeParse({ name: form.get("name") ?? "", template: form.get("template") ?? "", notes: form.get("notes") ?? "" });
  if (!b.success) for (const i of b.error.issues) fieldErrors[String(i.path[0])] ??= i.message;

  // Only the pairs the form showed (enabled ones); spreads for disabled pairs are kept.
  const pairs = (await db.select({ id: instruments.id, symbol: instruments.symbol }).from(instruments)).filter((p) =>
    form.has(`spread.${p.id}`),
  );
  const spreads: { instrumentId: string; typicalSpreadPips: string; symbolOverride: string | null }[] = [];
  for (const p of pairs) {
    const raw = String(form.get(`spread.${p.id}`) ?? "").trim();
    const over = Override.safeParse(form.get(`symbol.${p.id}`) ?? "");
    if (!over.success) fieldErrors[`symbol.${p.id}`] = over.error.issues[0]?.message ?? "Check the symbol.";
    if (raw === "") continue;
    const s = Spread.safeParse(raw);
    if (!s.success) fieldErrors[`spread.${p.id}`] = s.error.issues[0]?.message ?? "Check the spread.";
    else spreads.push({ instrumentId: p.id, typicalSpreadPips: String(s.data), symbolOverride: over.success && over.data ? over.data : null });
  }
  if (!b.success || Object.keys(fieldErrors).length) return { error: "Check the highlighted fields.", fieldErrors };

  const dupe = await db
    .select({ id: brokers.id })
    .from(brokers)
    .where(id ? and(eq(brokers.name, b.data.name), ne(brokers.id, id)) : eq(brokers.name, b.data.name));
  if (dupe.length) return { error: "Check the highlighted fields.", fieldErrors: { name: "Another broker has this name." } };

  const values = { name: b.data.name, platformUrlTemplate: b.data.template || null, notes: b.data.notes || null };
  const saved = await db.transaction(async (tx) => {
    let brokerId = id;
    let before: unknown = null;
    if (id) {
      const [old] = await tx.select().from(brokers).where(eq(brokers.id, id));
      if (!old) return null;
      before = { ...old, spreads: await tx.select().from(brokerSpreads).where(eq(brokerSpreads.brokerId, id)) };
      await tx.update(brokers).set(values).where(eq(brokers.id, id));
      if (pairs.length) {
        await tx
          .delete(brokerSpreads)
          .where(and(eq(brokerSpreads.brokerId, id), inArray(brokerSpreads.instrumentId, pairs.map((p) => p.id))));
      }
    } else {
      const [row] = await tx.insert(brokers).values(values).returning({ id: brokers.id });
      brokerId = row!.id;
    }
    if (spreads.length) await tx.insert(brokerSpreads).values(spreads.map((s) => ({ ...s, brokerId: brokerId! })));
    await audit(tx, { userId: admin.id, action: id ? "broker.update" : "broker.create", target: brokerId!, before, after: { ...values, spreads } });
    return brokerId;
  });
  if (!saved) return { error: "This broker doesn't exist." };
  revalidatePath("/settings/brokers");
  revalidatePath("/settings");
  return { ok: true, message: id ? "Broker saved" : `${b.data.name} added` };
}

/** Owners who used this broker fall back to reference prices (users.active_broker_id is set
 *  to null by the foreign key). */
export async function deleteBroker(_: BrokerState, form: FormData): Promise<BrokerState> {
  const admin = await requireAdmin();
  const id = z.uuid().safeParse(form.get("id"));
  if (!id.success) return { error: "This broker doesn't exist." };
  const gone = await db.transaction(async (tx) => {
    const [old] = await tx.delete(brokers).where(eq(brokers.id, id.data)).returning();
    if (old) await audit(tx, { userId: admin.id, action: "broker.delete", target: old.id, before: old });
    return old;
  });
  if (!gone) return { error: "This broker was already deleted." };
  revalidatePath("/settings/brokers");
  return { ok: true, message: `${gone.name} deleted` };
}
