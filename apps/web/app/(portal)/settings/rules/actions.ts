"use server";

import { and, eq, inArray, sql as dsql } from "drizzle-orm";
import { revalidatePath } from "next/cache";
import { z } from "zod";
import { audit } from "@/lib/audit";
import { db } from "@/lib/db";
import {
  instruments,
  ruleConfigRevision,
  ruleDefinitions,
  ruleVersions,
  strategyConfigs,
  strategyParamOverrides,
} from "@/lib/db/schema";
import { diffParams, validateOverride, validateParams, type Raw } from "@/lib/rule-params";
import { requireAdmin } from "@/lib/session";

export interface RuleActionState {
  ok?: boolean;
  message?: string;
  error?: string;
  fieldErrors?: Record<string, string>;
}

type Tx = Parameters<Parameters<typeof db.transaction>[0]>[0];

/** Every admin change bumps the revision so the worker reloads before the next bar. */
async function bumpRevision(tx: Tx) {
  await tx
    .update(ruleConfigRevision)
    .set({ revision: dsql`${ruleConfigRevision.revision} + 1`, updatedAt: new Date() })
    .where(eq(ruleConfigRevision.id, true));
}

function paramsFrom(form: FormData): Raw {
  const raw: Raw = {};
  for (const name of new Set([...form.keys()].filter((k) => k.startsWith("p.")))) {
    const values = form.getAll(name).map(String);
    raw[name.slice(2)] = values.length > 1 ? values : values[0];
  }
  return raw;
}

/** List parameters arrive as checkboxes; an unticked list sends nothing, so mark lists the
 *  form rendered. */
function withLists(raw: Raw, form: FormData): Raw {
  for (const name of form.getAll("lists").map(String)) {
    const v = raw[name];
    raw[name] = v === undefined ? [] : Array.isArray(v) ? v : [v];
  }
  return raw;
}

const Note = z.string().trim().min(1, "Write a change note.").max(500, "Keep the note under 500 characters.");
const Description = z.string().trim().min(1, "The description can't be empty.").max(2000, "Keep the description under 2000 characters.");

export async function saveRuleVersion(_: RuleActionState, form: FormData): Promise<RuleActionState> {
  const admin = await requireAdmin();
  const key = String(form.get("key") ?? "");
  const expected = Number(form.get("expectedVersion"));
  const approve = form.get("intent") === "approve";
  const note = Note.safeParse(form.get("note"));
  const description = Description.safeParse(form.get("description"));

  const [def] = await db.select().from(ruleDefinitions).where(eq(ruleDefinitions.key, key)).limit(1);
  if (!def) return { error: "This rule doesn't exist." };
  const [current] = await db
    .select()
    .from(ruleVersions)
    .where(and(eq(ruleVersions.key, key), eq(ruleVersions.version, def.currentVersion)))
    .limit(1);
  if (!current) return { error: "This rule has no current version." };

  const params = validateParams(current.paramsSchema, withLists(paramsFrom(form), form));
  const fieldErrors: Record<string, string> = params.ok ? {} : { ...params.errors };
  if (!note.success) fieldErrors.note = note.error.issues[0]?.message ?? "Write a change note.";
  if (!description.success) fieldErrors.description = description.error.issues[0]?.message ?? "Add a description.";
  if (!params.ok || !note.success || !description.success) {
    return { error: "Check the highlighted fields.", fieldErrors };
  }

  const next = {
    status: approve ? ("approved" as const) : current.status,
    enabled: form.get("enabled") === "on",
    countsTowardMinimum: def.kind === "indicator" ? form.get("counts") === "on" : current.countsTowardMinimum,
    description: description.data,
    params: params.params,
  };
  const unchanged =
    next.status === current.status &&
    next.enabled === current.enabled &&
    next.countsTowardMinimum === current.countsTowardMinimum &&
    next.description === current.description &&
    diffParams(current.params, next.params).length === 0;
  if (unchanged) return { error: "Nothing changed. Edit a value before saving a new version." };

  const result = await db.transaction(async (tx) => {
    const [locked] = await tx
      .select({ currentVersion: ruleDefinitions.currentVersion })
      .from(ruleDefinitions)
      .where(eq(ruleDefinitions.key, key))
      .for("update");
    if (!locked || locked.currentVersion !== expected) return { stale: true as const };
    const version = locked.currentVersion + 1;
    await tx.insert(ruleVersions).values({
      key,
      version,
      ...next,
      paramsSchema: current.paramsSchema,
      changeNote: note.data,
      createdBy: admin.id,
    });
    await tx.update(ruleDefinitions).set({ currentVersion: version }).where(eq(ruleDefinitions.key, key));
    await bumpRevision(tx);
    const snapshot = (v: { version: number; status: string; enabled: boolean; countsTowardMinimum: boolean; description: string; params: Record<string, unknown> }) => ({
      version: v.version,
      status: v.status,
      enabled: v.enabled,
      counts_toward_minimum: v.countsTowardMinimum,
      description: v.description,
      params: v.params,
    });
    await audit(tx, {
      userId: admin.id,
      action: approve ? "rule.approve" : "rule.update",
      target: key,
      before: snapshot(current),
      after: { ...snapshot({ ...next, version }), note: note.data },
    });
    return { version };
  });
  if ("stale" in result) return { error: "Someone saved a newer version. Reload the page to see it before saving." };
  revalidatePath("/settings/rules");
  return { ok: true, message: approve ? "Rule approved" : "Version saved" };
}

export async function setRuleOverride(_: RuleActionState, form: FormData): Promise<RuleActionState> {
  const admin = await requireAdmin();
  const key = String(form.get("key") ?? "");
  const instrumentId = z.uuid().safeParse(form.get("instrumentId"));
  if (!instrumentId.success) return { error: "Choose a pair." };
  const remove = form.get("intent") === "remove";

  const [def] = await db.select().from(ruleDefinitions).where(eq(ruleDefinitions.key, key)).limit(1);
  const [inst] = await db.select({ id: instruments.id, symbol: instruments.symbol }).from(instruments).where(eq(instruments.id, instrumentId.data));
  if (!def || !inst) return { error: "That rule or pair doesn't exist." };
  const [current] = await db
    .select({ schema: ruleVersions.paramsSchema })
    .from(ruleVersions)
    .where(and(eq(ruleVersions.key, key), eq(ruleVersions.version, def.currentVersion)));
  if (!current) return { error: "This rule has no current version." };

  let params: Record<string, unknown> = {};
  if (!remove) {
    const v = validateOverride(current.schema, paramsFrom(form));
    if (!v.ok) return { error: "Check the highlighted fields.", fieldErrors: v.errors };
    if (Object.keys(v.params).length === 0) return { error: "Fill in at least one value, or remove the override." };
    params = v.params;
  }

  await db.transaction(async (tx) => {
    const [before] = await tx
      .select({ params: strategyParamOverrides.params })
      .from(strategyParamOverrides)
      .where(and(eq(strategyParamOverrides.key, key), eq(strategyParamOverrides.instrumentId, inst.id)));
    if (remove) {
      await tx
        .delete(strategyParamOverrides)
        .where(and(eq(strategyParamOverrides.key, key), eq(strategyParamOverrides.instrumentId, inst.id)));
    } else {
      await tx
        .insert(strategyParamOverrides)
        .values({ key, instrumentId: inst.id, params, updatedBy: admin.id })
        .onConflictDoUpdate({
          target: [strategyParamOverrides.key, strategyParamOverrides.instrumentId],
          set: { params, updatedBy: admin.id, updatedAt: new Date() },
        });
    }
    await bumpRevision(tx);
    await audit(tx, {
      userId: admin.id,
      action: remove ? "rule.override.remove" : "rule.override",
      target: `${key} ${inst.symbol}`,
      before: before?.params ?? null,
      after: remove ? null : params,
    });
  });
  revalidatePath("/settings/rules");
  return { ok: true, message: remove ? `Override for ${inst.symbol} removed` : `Override for ${inst.symbol} saved` };
}

const STRATEGIES = ["three_eight", "fib_pivot", "stocks"] as const;

/** The per-strategy switch and the pairs it scans (decision 2026-10-01, strategy_configs). */
export async function setStrategyConfig(_: RuleActionState, form: FormData): Promise<RuleActionState> {
  const admin = await requireAdmin();
  const strategy = z.enum(STRATEGIES).safeParse(form.get("strategy"));
  if (!strategy.success) return { error: "That strategy doesn't exist." };
  const enabled = form.get("enabled") === "on";
  let instrumentIds: string[] | null = null;
  if (strategy.data !== "stocks" && form.get("pairs") === "some") {
    const ids = z.array(z.uuid()).safeParse(form.getAll("instrumentIds"));
    if (!ids.success || ids.data.length === 0) return { error: "Choose at least one pair, or scan all pairs." };
    const found = await db.select({ id: instruments.id }).from(instruments).where(inArray(instruments.id, ids.data));
    if (found.length !== ids.data.length) return { error: "One of those pairs doesn't exist." };
    instrumentIds = ids.data;
  }
  await db.transaction(async (tx) => {
    const [before] = await tx.select().from(strategyConfigs).where(eq(strategyConfigs.strategy, strategy.data));
    await tx
      .update(strategyConfigs)
      .set({ enabled, instrumentIds, updatedBy: admin.id, updatedAt: new Date() })
      .where(eq(strategyConfigs.strategy, strategy.data));
    await bumpRevision(tx);
    await audit(tx, {
      userId: admin.id,
      action: "strategy.update",
      target: strategy.data,
      before: before ? { enabled: before.enabled, instrument_ids: before.instrumentIds } : null,
      after: { enabled, instrument_ids: instrumentIds },
    });
  });
  revalidatePath("/settings/rules");
  return { ok: true, message: "Strategy settings saved" };
}
