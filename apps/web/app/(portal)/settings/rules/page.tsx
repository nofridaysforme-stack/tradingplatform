import type { Metadata } from "next";
import Link from "next/link";
import { Badge, ProvisionalBadge } from "@/components/ui";
import { forexEnabled } from "@/lib/app-settings";
import { nyDateTime, pips } from "@/lib/format";
import type { Summary } from "@/lib/metrics";
import { diffParams, paramLabel, showValue } from "@/lib/rule-params";
import {
  forexPairs,
  getRule,
  listRules,
  listStrategyConfigs,
  RULE_STRATEGY_NAMES,
  STRATEGY_ORDER,
  type RuleDetail,
  type RuleListItem,
} from "@/lib/rules";
import { requireAdmin } from "@/lib/session";
import { Overrides } from "./overrides";
import { RuleEditor } from "./rule-editor";
import { StrategySwitch } from "./strategy-switch";

export const metadata: Metadata = { title: "Rules · Trading desk" };

const KIND_NAMES: Record<string, string> = {
  indicator: "Indicator",
  gate: "Gate",
  plan: "Trade plan",
  filter: "Filter",
  lifecycle: "Lifecycle",
};

export default async function RulesPage({ searchParams }: PageProps<"/settings/rules">) {
  await requireAdmin();
  const { rule: selectedKey } = await searchParams;
  const key = typeof selectedKey === "string" ? selectedKey : undefined;
  const [rules, configs, pairs, detail, forex] = await Promise.all([
    listRules(),
    listStrategyConfigs(),
    forexPairs(),
    key ? getRule(key) : Promise.resolve(null),
    forexEnabled(),
  ]);

  return (
    <main>
      <nav className="px-5 pt-4">
        <Link href="/settings" className="inline-flex min-h-11 items-center text-sm text-link">
          <span aria-hidden="true">‹&nbsp;</span>Settings
        </Link>
      </nav>
      <header className="px-5 pt-1.5 pb-3.5">
        <h1 className="m-0 text-[22px] font-semibold leading-tight">Rules</h1>
        <p className="m-0 mt-1 max-w-[62ch] text-[13px] text-mute">
          Every change saves a new version. The scanner picks it up from the next bar, and signals record the versions they used.
        </p>
      </header>

      <div className="border-t border-rule lg:grid lg:grid-cols-[300px_minmax(0,1fr)]">
        <div className={`lg:border-r lg:border-rule ${detail ? "hidden lg:block" : ""}`}>
          {/* While forex is paused only the stock rules are listed (decision 2026-10-08). */}
          {STRATEGY_ORDER.filter((strategy) => forex || strategy === "stocks").map((strategy) => {
            const config = configs.find((c) => c.strategy === strategy);
            const group = rules.filter((r) => r.strategy === strategy);
            if (group.length === 0) return null;
            const name = RULE_STRATEGY_NAMES[strategy];
            return (
              <section key={strategy} aria-labelledby={`group-${strategy}`} className="border-b border-rule px-5 pt-4">
                <h2 id={`group-${strategy}`} className="m-0 mb-1 text-base font-semibold">
                  {name}
                </h2>
                {config && (
                  <StrategySwitch
                    strategy={strategy}
                    name={name}
                    enabled={config.enabled}
                    instrumentIds={config.instrumentIds}
                    pairs={pairs}
                  />
                )}
                <RuleList rules={group} selected={key} />
              </section>
            );
          })}
        </div>

        <div className={detail ? "" : "hidden lg:block"}>
          {key && !detail && <p className="m-0 px-5 py-5 text-sm text-ink-2">That rule doesn&apos;t exist. Choose one from the list.</p>}
          {!key && <p className="m-0 px-5 py-5 text-sm text-ink-2">Choose a rule to see its parameters, history, and results.</p>}
          {detail && <Editor rule={detail} pairs={pairs} />}
        </div>
      </div>
    </main>
  );
}

function RuleList({ rules, selected }: { rules: RuleListItem[]; selected?: string }) {
  return (
    <ul className="m-0 -mx-5 list-none p-0">
      {rules.map((r) => {
        const on = r.key === selected;
        return (
          <li key={r.key}>
            <Link
              href={`/settings/rules?rule=${encodeURIComponent(r.key)}`}
              aria-current={on ? "page" : undefined}
              className={`flex min-h-11 items-center justify-between gap-2 border-t border-rule-soft px-5 py-2 text-sm text-ink no-underline ${on ? "bg-selected" : "hover:bg-selected"}`}
            >
              <span className="min-w-0">
                <span className={on ? "font-semibold" : ""}>{r.name}</span>
                <span className="block text-xs text-mute">
                  {KIND_NAMES[r.kind] ?? r.kind} · v{r.version}
                  {!r.enabled && " · Off"}
                </span>
              </span>
              {r.status === "provisional" && <ProvisionalBadge />}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function Editor({ rule, pairs }: { rule: RuleDetail; pairs: { id: string; symbol: string }[] }) {
  const c = rule.current;
  return (
    <div>
      <nav className="px-5 pt-3 lg:hidden">
        <Link href="/settings/rules" className="inline-flex min-h-11 items-center text-sm text-link">
          <span aria-hidden="true">‹&nbsp;</span>All rules
        </Link>
      </nav>
      <section aria-labelledby="rule-h" className="px-5 pt-4 pb-5">
        <h2 id="rule-h" className="m-0 text-lg font-semibold">
          {rule.name}
        </h2>
        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[13px] text-mute">
          {c.status === "provisional" ? <ProvisionalBadge /> : <Badge kind="state">Approved</Badge>}
          <span>
            {RULE_STRATEGY_NAMES[rule.strategy]} · {KIND_NAMES[rule.kind] ?? rule.kind} · Version {c.version}
            {!c.enabled && " · Off"}
          </span>
        </div>
        <p className="m-0 mt-2 text-[13px] text-mute">
          Source: {rule.source} · <code className="font-[inherit]">{rule.key}</code>
        </p>
        <div className="mt-3">
          <RuleEditor
            ruleKey={rule.key}
            name={rule.name}
            kind={rule.kind}
            schema={rule.schema}
            version={c.version}
            status={c.status}
            enabled={c.enabled}
            countsTowardMinimum={c.countsTowardMinimum}
            description={c.description}
            params={c.params}
          />
        </div>
      </section>

      <section aria-labelledby="perf-h" className="border-t border-rule px-5 py-5">
        <h2 id="perf-h" className="m-0 mb-1 text-base font-semibold">
          Performance
        </h2>
        <p className="m-0 mb-3 text-[13px] text-mute">Closed signals that used this rule, on reference prices. Invalidated signals are left out.</p>
        <PerfTable rule={rule} />
      </section>

      <section aria-labelledby="overrides-h" className="border-t border-rule px-5 py-5">
        <h2 id="overrides-h" className="m-0 mb-3 text-base font-semibold">
          Per-pair overrides
        </h2>
        <Overrides ruleKey={rule.key} schema={rule.schema} overrides={rule.overrides} pairs={pairs} />
      </section>

      <section aria-labelledby="versions-h" className="border-t border-rule px-5 py-5">
        <h2 id="versions-h" className="m-0 mb-3 text-base font-semibold">
          Version history
        </h2>
        <ol className="m-0 list-none p-0">
          {rule.versions.map((v, i) => {
            const prev = rule.versions[i + 1];
            const changes = prev ? diffParams(prev.params, v.params) : [];
            const flags = prev
              ? [
                  prev.status !== v.status && `Status ${prev.status} to ${v.status}`,
                  prev.enabled !== v.enabled && (v.enabled ? "Turned on" : "Turned off"),
                  prev.countsTowardMinimum !== v.countsTowardMinimum &&
                    (v.countsTowardMinimum ? "Now counts toward the minimum" : "No longer counts toward the minimum"),
                  prev.description !== v.description && "Description changed",
                ].filter(Boolean)
              : [];
            return (
              <li key={v.version} className="border-b border-rule-soft py-3 text-sm">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <span className="font-semibold">
                    Version {v.version}
                    {v.version === rule.current.version && <span className="ml-2 font-normal text-mute">Current</span>}
                  </span>
                  <span className="text-[13px] text-mute">
                    {nyDateTime(new Date(v.createdAt))} NY{v.createdBy ? ` · ${v.createdBy}` : ""}
                  </span>
                </div>
                <p className="m-0 mt-0.5 text-[13px] text-ink-2">
                  {v.status === "provisional" ? "Provisional" : "Approved"}
                  {v.changeNote ? ` · ${v.changeNote}` : ""}
                </p>
                {(changes.length > 0 || flags.length > 0) && (
                  <ul className="m-0 mt-1.5 list-none p-0 text-[13px]">
                    {flags.map((f) => (
                      <li key={String(f)} className="text-ink-2">
                        {f}
                      </li>
                    ))}
                    {changes.map((ch) => (
                      <li key={ch.name} className="text-ink-2">
                        {paramLabel(ch.name)}: <span className="text-mute line-through">{showValue(ch.before)}</span>{" "}
                        <span aria-hidden="true">→</span>
                        <span className="sr-only">changed to</span> <span className="text-ink">{showValue(ch.after)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ol>
      </section>
    </div>
  );
}

function PerfTable({ rule }: { rule: RuleDetail }) {
  const rows: [string, Summary][] = [["All signals using it", rule.performance.using]];
  if (rule.performance.fired && rule.performance.notFired) {
    rows.push(["When it fired", rule.performance.fired], ["When it did not fire", rule.performance.notFired]);
  }
  return (
    <table className="w-full border-collapse font-condensed text-sm">
      <thead>
        <tr className="text-xs text-mute">
          <th scope="col" className="pb-1.5 text-left font-normal">
            <span className="sr-only">Group</span>
          </th>
          <th scope="col" className="pb-1.5 text-right font-normal">
            Trades
          </th>
          <th scope="col" className="pb-1.5 text-right font-normal">
            Win rate
          </th>
          <th scope="col" className="pb-1.5 text-right font-normal">
            Net pips
          </th>
          <th scope="col" className="pb-1.5 text-right font-normal">
            Expectancy
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, s]) => (
          <tr key={label} className="border-t border-rule-soft">
            <th scope="row" className="py-2 text-left font-normal text-ink-2">
              {label}
            </th>
            <td className="py-2 text-right">{s.trades}</td>
            <td className="py-2 text-right">{s.trades ? `${Math.round(s.winRate * 100)}%` : ""}</td>
            <td className="py-2 text-right">{s.trades ? pips(s.netPips) : ""}</td>
            <td className="py-2 text-right">{s.trades ? pips(s.expectancy) : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
