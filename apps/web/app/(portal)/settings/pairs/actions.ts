"use server";

import { eq, max } from "drizzle-orm";
import { revalidatePath } from "next/cache";
import { z } from "zod";
import { audit } from "@/lib/audit";
import { db } from "@/lib/db";
import { instruments } from "@/lib/db/schema";
import { displayDecimals, normalizePair, PIP_SIZES, providerCode } from "@/lib/pairs";
import { requireAdmin } from "@/lib/session";

export interface PairState {
  ok?: boolean;
  message?: string;
  error?: string;
  fieldErrors?: Record<string, string>;
}

/** Adds a forex pair. The worker backfills its history within five minutes
 *  (new_pair_backfill), and it is scanned from the next bar. */
export async function addPair(_: PairState, form: FormData): Promise<PairState> {
  const admin = await requireAdmin();
  const symbol = normalizePair(String(form.get("symbol") ?? ""));
  const pip = z.enum(PIP_SIZES).safeParse(form.get("pipSize"));
  const fieldErrors: Record<string, string> = {};
  if (!symbol) fieldErrors.symbol = "Enter a pair like EUR/GBP.";
  if (!pip.success) fieldErrors.pipSize = "Choose a pip size.";
  if (!symbol || !pip.success) return { error: "Check the highlighted fields.", fieldErrors };
  const [exists] = await db.select({ id: instruments.id }).from(instruments).where(eq(instruments.symbol, symbol));
  if (exists) return { error: "Check the highlighted fields.", fieldErrors: { symbol: `${symbol} is already in the list.` } };
  await db.transaction(async (tx) => {
    const [{ last } = { last: 0 }] = await tx.select({ last: max(instruments.sortOrder) }).from(instruments);
    const values = {
      symbol,
      providerCode: providerCode(symbol),
      assetClass: "forex",
      pipSize: pip.data,
      displayDecimals: displayDecimals(pip.data),
      sortOrder: (last ?? 0) + 1,
    };
    const [row] = await tx.insert(instruments).values(values).returning({ id: instruments.id });
    await audit(tx, { userId: admin.id, action: "instrument.add", target: row!.id, after: values });
  });
  revalidatePath("/settings/pairs");
  return { ok: true, message: `${symbol} added. Its history loads within a few minutes.` };
}

/** Turn a pair on or off and set its place in lists. */
export async function updatePair(_: PairState, form: FormData): Promise<PairState> {
  const admin = await requireAdmin();
  const id = z.uuid().safeParse(form.get("id"));
  const order = z.coerce.number().int().min(0).max(999).safeParse(form.get("sortOrder"));
  if (!id.success) return { error: "This pair doesn't exist." };
  if (!order.success) return { error: "Use a whole number from 0 to 999 for the order." };
  const enabled = form.get("enabled") === "on";
  const done = await db.transaction(async (tx) => {
    const [before] = await tx.select().from(instruments).where(eq(instruments.id, id.data));
    if (!before) return null;
    await tx.update(instruments).set({ enabled, sortOrder: order.data }).where(eq(instruments.id, id.data));
    await audit(tx, {
      userId: admin.id,
      action: "instrument.update",
      target: before.symbol,
      before: { enabled: before.enabled, sort_order: before.sortOrder },
      after: { enabled, sort_order: order.data },
    });
    return before.symbol;
  });
  if (!done) return { error: "This pair doesn't exist." };
  revalidatePath("/settings/pairs");
  return { ok: true, message: `${done} saved` };
}
