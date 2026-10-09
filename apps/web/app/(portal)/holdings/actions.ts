"use server";

import { and, eq } from "drizzle-orm";
import { revalidatePath } from "next/cache";
import { z } from "zod";
import { db } from "@/lib/db";
import { holdings } from "@/lib/db/schema";
import { requireUser } from "@/lib/session";

export interface HoldingState {
  ok?: boolean;
  message?: string;
  error?: string;
  fieldErrors?: Record<string, string>;
}

const today = () => new Date().toISOString().slice(0, 10);

const Holding = z.object({
  ticker: z
    .string()
    .trim()
    .toUpperCase()
    .regex(/^[A-Z][A-Z0-9.\-]{0,9}$/, "Enter a ticker, for example AAPL."),
  purchasePrice: z.coerce.number({ error: "Enter the price you paid." }).positive("Enter the price you paid.").max(1_000_000, "Check the price."),
  purchaseDate: z.iso
    .date("Enter the purchase date.")
    .refine((d) => d <= today(), "The purchase date can't be in the future.")
    .refine((d) => d >= "1990-01-01", "Check the purchase date."),
  // Ranges from the stocks.momentum rule schema (projection_pct, horizon_sessions).
  expectedProfitPct: z.coerce.number({ error: "Enter a percentage." }).min(1, "Use 1 or more.").max(1000, "Use 1000 or less."),
  horizonSessions: z.coerce.number({ error: "Enter a number of sessions." }).int("Enter a whole number.").min(1, "Use 1 or more.").max(260, "Use 260 or less."),
  notes: z.string().trim().max(500, "Keep notes under 500 characters.").optional(),
});

function parse(form: FormData) {
  const r = Holding.safeParse({
    ticker: form.get("ticker") ?? "",
    purchasePrice: form.get("purchasePrice") || undefined,
    purchaseDate: form.get("purchaseDate") ?? "",
    expectedProfitPct: form.get("expectedProfitPct") || undefined,
    horizonSessions: form.get("horizonSessions") || undefined,
    notes: (form.get("notes") as string | null) || undefined,
  });
  if (r.success) return { data: r.data };
  const fieldErrors: Record<string, string> = {};
  for (const issue of r.error.issues) {
    const k = String(issue.path[0]);
    fieldErrors[k] ??= issue.message;
  }
  return { fieldErrors };
}

const values = (d: z.infer<typeof Holding>) => ({
  ticker: d.ticker,
  purchasePrice: String(d.purchasePrice),
  purchaseDate: d.purchaseDate,
  expectedProfitPct: String(d.expectedProfitPct),
  horizonSessions: d.horizonSessions,
  notes: d.notes ?? null,
});

export async function createHolding(_: HoldingState, form: FormData): Promise<HoldingState> {
  const user = await requireUser();
  const p = parse(form);
  if (!p.data) return { error: "Check the highlighted fields.", fieldErrors: p.fieldErrors };
  await db.insert(holdings).values({ userId: user.id, ...values(p.data) });
  revalidatePath("/holdings");
  return { ok: true, message: `${p.data.ticker} added` };
}

/** Owners edit only their own holdings. */
export async function updateHolding(_: HoldingState, form: FormData): Promise<HoldingState> {
  const user = await requireUser();
  const id = z.uuid().safeParse(form.get("id"));
  if (!id.success) return { error: "This holding doesn't exist." };
  const p = parse(form);
  if (!p.data) return { error: "Check the highlighted fields.", fieldErrors: p.fieldErrors };
  const done = await db
    .update(holdings)
    .set(values(p.data))
    .where(and(eq(holdings.id, id.data), eq(holdings.userId, user.id)))
    .returning({ id: holdings.id });
  if (done.length === 0) return { error: "This holding doesn't exist." };
  revalidatePath("/holdings");
  return { ok: true, message: "Changes saved" };
}

export async function closeHolding(_: HoldingState, form: FormData): Promise<HoldingState> {
  const user = await requireUser();
  const id = z.uuid().safeParse(form.get("id"));
  if (!id.success) return { error: "This holding doesn't exist." };
  const done = await db
    .update(holdings)
    .set({ closed: true })
    .where(and(eq(holdings.id, id.data), eq(holdings.userId, user.id), eq(holdings.closed, false)))
    .returning({ ticker: holdings.ticker });
  if (done.length === 0) return { error: "This holding is already closed." };
  revalidatePath("/holdings");
  return { ok: true, message: `${done[0]!.ticker} closed` };
}
