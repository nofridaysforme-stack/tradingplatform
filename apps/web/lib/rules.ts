import "server-only";
import { and, asc, desc, eq, notInArray, sql as dsql } from "drizzle-orm";
import { db } from "@/lib/db";
import {
  instruments,
  ruleDefinitions,
  ruleVersions,
  signalIndicators,
  signals,
  strategyConfigs,
  strategyParamOverrides,
  users,
} from "@/lib/db/schema";
import { summarize, type Summary } from "@/lib/metrics";
import type { ParamsSchema } from "@/lib/rule-params";

export type RuleStrategy = "three_eight" | "fib_pivot" | "stocks";
export const STRATEGY_ORDER: RuleStrategy[] = ["three_eight", "fib_pivot", "stocks"];
export const RULE_STRATEGY_NAMES: Record<RuleStrategy, string> = {
  three_eight: "3/8 system",
  fib_pivot: "Fib Pivot",
  stocks: "Stock screener",
};
const KIND_ORDER = ["indicator", "gate", "plan", "filter", "lifecycle"];

export interface RuleListItem {
  key: string;
  strategy: RuleStrategy;
  kind: string;
  name: string;
  version: number;
  status: "approved" | "provisional";
  enabled: boolean;
}

export async function listRules(): Promise<RuleListItem[]> {
  const rows = await db
    .select({
      key: ruleDefinitions.key,
      strategy: ruleDefinitions.strategy,
      kind: ruleDefinitions.kind,
      name: ruleDefinitions.name,
      version: ruleVersions.version,
      status: ruleVersions.status,
      enabled: ruleVersions.enabled,
    })
    .from(ruleDefinitions)
    .innerJoin(ruleVersions, and(eq(ruleVersions.key, ruleDefinitions.key), eq(ruleVersions.version, ruleDefinitions.currentVersion)))
    .orderBy(asc(ruleDefinitions.key));
  return rows.sort(
    (a, b) =>
      STRATEGY_ORDER.indexOf(a.strategy) - STRATEGY_ORDER.indexOf(b.strategy) ||
      KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind) ||
      a.name.localeCompare(b.name),
  );
}

export interface RuleVersionView {
  version: number;
  status: "approved" | "provisional";
  enabled: boolean;
  countsTowardMinimum: boolean;
  description: string;
  params: Record<string, unknown>;
  changeNote: string | null;
  createdAt: string;
  createdBy: string | null;
}

export interface Performance {
  using: Summary;
  fired?: Summary;
  notFired?: Summary;
}

export interface RuleDetail {
  key: string;
  strategy: RuleStrategy;
  kind: string;
  name: string;
  source: string;
  schema: ParamsSchema;
  current: RuleVersionView;
  versions: RuleVersionView[];
  overrides: { instrumentId: string; symbol: string; params: Record<string, unknown>; updatedAt: string }[];
  performance: Performance;
}

export async function getRule(key: string): Promise<RuleDetail | null> {
  const [def] = await db.select().from(ruleDefinitions).where(eq(ruleDefinitions.key, key)).limit(1);
  if (!def) return null;
  const [versions, overrides, performance] = await Promise.all([
    db
      .select({ v: ruleVersions, by: users.email })
      .from(ruleVersions)
      .leftJoin(users, eq(users.id, ruleVersions.createdBy))
      .where(eq(ruleVersions.key, key))
      .orderBy(desc(ruleVersions.version)),
    db
      .select({ instrumentId: strategyParamOverrides.instrumentId, symbol: instruments.symbol, params: strategyParamOverrides.params, updatedAt: strategyParamOverrides.updatedAt })
      .from(strategyParamOverrides)
      .innerJoin(instruments, eq(instruments.id, strategyParamOverrides.instrumentId))
      .where(eq(strategyParamOverrides.key, key))
      .orderBy(asc(instruments.sortOrder), asc(instruments.symbol)),
    rulePerformance(key, def.kind),
  ]);
  const views: RuleVersionView[] = versions.map(({ v, by }) => ({
    version: v.version,
    status: v.status,
    enabled: v.enabled,
    countsTowardMinimum: v.countsTowardMinimum,
    description: v.description,
    params: v.params,
    changeNote: v.changeNote,
    createdAt: v.createdAt.toISOString(),
    createdBy: by,
  }));
  const current = views.find((v) => v.version === def.currentVersion);
  const schema = versions.find(({ v }) => v.version === def.currentVersion)?.v.paramsSchema;
  if (!current || !schema) return null;
  return {
    key: def.key,
    strategy: def.strategy,
    kind: def.kind,
    name: def.name,
    source: def.source,
    schema,
    current,
    versions: views,
    overrides: overrides.map((o) => ({ ...o, updatedAt: o.updatedAt.toISOString() })),
    performance,
  };
}

/** Outcomes of closed signals whose version set includes this rule; for an indicator, split
 *  by whether it fired (the spec 12 input for approving provisional rules). */
async function rulePerformance(key: string, kind: string): Promise<Performance> {
  const rows = await db
    .select({
      state: signals.state,
      resultPips: signals.resultPips,
      fired: signalIndicators.fired,
    })
    .from(signals)
    .leftJoin(signalIndicators, and(eq(signalIndicators.signalId, signals.id), eq(signalIndicators.key, key)))
    .where(
      and(
        notInArray(signals.state, ["open", "confirmed", "invalidated"]),
        dsql`${signals.versionSet} ? ${key}`,
        dsql`${signals.resultPips} is not null`,
      ),
    );
  const trades = rows.map((r) => ({ state: r.state, resultPips: Number(r.resultPips), fired: r.fired === true }));
  const perf: Performance = { using: summarize(trades) };
  if (kind === "indicator") {
    perf.fired = summarize(trades.filter((t) => t.fired));
    perf.notFired = summarize(trades.filter((t) => !t.fired));
  }
  return perf;
}

export interface StrategyConfigView {
  strategy: RuleStrategy;
  enabled: boolean;
  instrumentIds: string[] | null;
}

export async function listStrategyConfigs(): Promise<StrategyConfigView[]> {
  const rows = await db.select().from(strategyConfigs);
  return STRATEGY_ORDER.flatMap((s) => {
    const r = rows.find((x) => x.strategy === s);
    return r ? [{ strategy: s, enabled: r.enabled, instrumentIds: r.instrumentIds }] : [];
  });
}

export async function forexPairs() {
  return db
    .select({ id: instruments.id, symbol: instruments.symbol, enabled: instruments.enabled })
    .from(instruments)
    .where(eq(instruments.assetClass, "forex"))
    .orderBy(asc(instruments.sortOrder), asc(instruments.symbol));
}

