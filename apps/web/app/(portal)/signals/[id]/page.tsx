import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { z } from "zod";
import { INDICATORS, IndicatorRing, ringStates } from "@/components/ring";
import { SignalChart } from "@/components/signal-chart";
import { Badge, DirectionMarker, ProvisionalBadge } from "@/components/ui";
import { age, nyDateTime, nyTime, pips, ratio, STATE_NAMES, STRATEGY_NAMES } from "@/lib/format";
import { requireUser } from "@/lib/session";
import { activeBroker, getSignal, type SignalDetail } from "@/lib/signals";
import { AdminActions } from "./admin-actions";

export const metadata: Metadata = { title: "Signal · Trading desk" };

const PROVISIONAL_NOTE = "Provisional: this definition is waiting for owner approval.";

const EVENT_NAMES: Record<string, string> = {
  created: "Created",
  confirmed: "Confirmed",
  reset_reached: "Reset reached",
  target_hit: "Target hit",
  stop_hit: "Stop hit",
  expired: "Expired",
  invalidated: "Marked invalid",
  ambiguous: "Closed, stop and target in one bar",
  note: "Note",
};

export default async function SignalPage({ params }: PageProps<"/signals/[id]">) {
  const user = await requireUser();
  const { id } = await params;
  if (!z.uuid().safeParse(id).success) notFound();
  const broker = await activeBroker(user.activeBrokerId);
  const s = await getSignal(id, broker);
  if (!s) notFound();
  const now = new Date();
  const created = new Date(s.created_at);
  return (
    <main>
      <nav className="px-5 pt-4">
        <Link href="/dashboard" className="inline-flex min-h-11 items-center text-sm text-link">
          <span aria-hidden="true">‹&nbsp;</span>Signals
        </Link>
      </nav>
      <header className="px-5 pt-1.5 pb-3.5">
        <h1 className="m-0 flex flex-wrap items-baseline gap-x-3 text-[28px] font-semibold leading-tight tracking-[-0.01em]">
          <DirectionMarker direction={s.direction} large />
          <span>{s.instrument}</span>
        </h1>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-[13px] text-mute">
          <span className="text-ink-2">{STRATEGY_NAMES[s.strategy]}</span>
          <Badge kind="state">{STATE_NAMES[s.state]}</Badge>
          {s.has_provisional && <ProvisionalBadge />}
          {s.confluence && (
            <Badge kind="confluence">
              <span aria-hidden="true">◆ </span>Both systems agree
            </Badge>
          )}
          <span>
            Created {nyTime(created)} NY · {age(created, now)}
          </span>
        </div>
        {s.confluence_id && (
          <p className="m-0 mt-1.5 text-[13px]">
            <Link href={`/signals/${s.confluence_id}`} className="text-link">
              See the {s.strategy === "three_eight" ? "Fib Pivot" : "3/8 system"} signal
            </Link>
          </p>
        )}
      </header>

      <TradePlan s={s} brokerName={broker?.name ?? null} />
      {s.closed_at && s.result_pips !== null && <Outcome s={s} />}
      <Why s={s} />

      <section aria-labelledby="chart-h" className="border-t border-rule px-5 py-5">
        <h2 id="chart-h" className="m-0 mb-3 text-base font-semibold">
          Chart
        </h2>
        <SignalChart signal={s} />
      </section>

      <Timeline s={s} />
      {user.role === "admin" && <AdminActions signalId={s.id} canInvalidate={s.state !== "invalidated"} />}
    </main>
  );
}

function TradePlan({ s, brokerName }: { s: SignalDetail; brokerName: string | null }) {
  const a = s.adjusted;
  const rows: [string, string, string | undefined][] = [
    ["Entry", s.reference.entry, a?.entry],
    ["Stop", s.reference.stop, a?.stop],
    ["Target", s.reference.target, a?.target],
  ];
  return (
    <section aria-labelledby="plan-h" className="border-t border-rule px-5 py-5">
      <h2 id="plan-h" className="m-0 mb-3 text-base font-semibold">
        Trade plan
      </h2>
      <table className="w-full border-collapse text-[15px]">
        <thead>
          <tr className="text-xs text-mute">
            <th scope="col" className="pb-1.5 text-left font-normal">
              <span className="sr-only">Level</span>
            </th>
            <th scope="col" className="pb-1.5 pl-[22px] text-right font-normal">
              Reference
            </th>
            {a && (
              <th scope="col" className="pb-1.5 pl-[22px] text-right font-normal">
                {a.broker}
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, ref, adj]) => (
            <tr key={label} className={label === "Entry" ? "font-semibold" : ""}>
              <th scope="row" className={`py-1 text-left text-ink-2 ${label === "Entry" ? "font-semibold" : "font-normal"}`}>
                {label}
              </th>
              <td className="py-1 pl-[22px] text-right">{ref}</td>
              {a && <td className="py-1 pl-[22px] text-right">{adj}</td>}
            </tr>
          ))}
          {s.alt_target && (
            <tr>
              <th scope="row" className="py-1 text-left font-normal text-ink-2">
                Alternative target
              </th>
              <td className="py-1 pl-[22px] text-right">{s.alt_target}</td>
              {a && (
                <td className="py-1 pl-[22px] text-right">
                  <span className="sr-only">Not adjusted</span>
                </td>
              )}
            </tr>
          )}
        </tbody>
      </table>
      <p className="m-0 mt-3 text-sm text-ink-2">
        Risk {s.risk_pips} pips · Reward {s.reward_pips} pips · R:R {ratio(s.reference.reward_risk)}
        {a && <> ({ratio(a.reward_risk)} with {a.broker})</>}
      </p>
      {!a && (
        <p className="m-0 mt-1.5 text-[13px] text-mute">
          {brokerName
            ? `Reference prices. ${brokerName} has no spread set for ${s.instrument} yet.`
            : "Reference prices. Choose a broker in Settings to see adjusted prices."}
        </p>
      )}
      {s.broker_link && a && (
        <a
          href={s.broker_link}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 flex h-12 w-full items-center justify-center rounded-control bg-ink text-[15px] font-semibold text-bg no-underline"
        >
          Open in {a.broker}
        </a>
      )}
    </section>
  );
}

function Outcome({ s }: { s: SignalDetail }) {
  return (
    <section aria-labelledby="outcome-h" className="border-t border-rule px-5 py-5">
      <h2 id="outcome-h" className="m-0 mb-2 text-base font-semibold">
        Outcome
      </h2>
      <p className="m-0 text-sm text-ink-2">
        <strong className="text-[17px] font-semibold text-ink">{pips(s.result_pips ?? 0)} pips</strong> on reference prices
        {s.exit_price && <>, closed at {s.exit_price}</>}
        {s.closed_at && <> on {nyDateTime(new Date(s.closed_at))} NY</>}
      </p>
      {s.adjusted_result_pips !== null && s.adjusted && (
        <p className="m-0 mt-1 text-sm text-ink-2">
          {pips(s.adjusted_result_pips)} pips after the {s.adjusted.broker} spread
        </p>
      )}
    </section>
  );
}

const humanize = (k: string) => {
  const t = k.replaceAll("_", " ").replaceAll(".", " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
};

function detailText(detail: Record<string, unknown>, decimals: number): string {
  return Object.entries(detail)
    .filter(([, v]) => v !== null && v !== undefined && typeof v !== "object")
    .map(([k, v]) => {
      const value = typeof v === "number" && !Number.isInteger(v) ? v.toFixed(k.includes("pips") ? 1 : decimals) : String(v);
      return `${humanize(k)} ${value.replaceAll("_", " ")}`;
    })
    .join(" · ");
}

function Why({ s }: { s: SignalDetail }) {
  const byKey = new Map(s.indicators.map((i) => [i.key, i]));
  const ring = s.strategy === "three_eight";
  const list = ring
    ? INDICATORS.map((ind) => ({ ...ind, row: byKey.get(ind.key) }))
    : s.indicators.map((i) => ({ key: i.key, name: i.name, short: i.name, row: i }));
  const states = ringStates(s.indicators);
  return (
    <section aria-labelledby="why-h" className="border-t border-rule px-5 py-5">
      <h2 id="why-h" className="m-0 mb-4 text-base font-semibold">
        Why
      </h2>
      {ring && (
        <div className="mb-4 flex items-center gap-4">
          <IndicatorRing states={states} direction={s.direction} size={112} />
          <p className="m-0 text-sm text-ink-2">
            {s.indicator_count ?? 0} of 8 indicators fired
            {s.minimum !== null && <>; {s.minimum} needed</>}.
          </p>
        </div>
      )}
      <ol className="m-0 list-none p-0">
        {list.map((ind, n) => {
          const r = ind.row;
          const fired = r?.fired ?? false;
          return (
            <li key={ind.key} className="flex gap-3 border-b border-rule-soft py-2.5">
              {ring && <span className="w-4 flex-none text-[13px] text-mute">{n + 1}</span>}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <span className="text-sm font-medium text-ink">{ind.name}</span>
                  <span className={`text-[13px] ${fired ? "text-ink" : "text-mute"}`}>{fired ? "Fired" : "Not fired"}</span>
                </div>
                {fired && r && (r.level_ref || Object.keys(r.detail).length > 0) && (
                  <p className="m-0 mt-0.5 text-[13px] text-ink-2">
                    {[r.level_ref ? humanize(r.level_ref) : "", detailText(r.detail, s.decimals)].filter(Boolean).join(" · ")}
                  </p>
                )}
                {r?.provisional && (
                  <p className="m-0 mt-1 flex flex-wrap items-center gap-2 text-[13px] text-ink-2">
                    <ProvisionalBadge />
                    {PROVISIONAL_NOTE}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      {s.gates.length > 0 && (
        <>
          <h3 className="m-0 mt-5 mb-1 text-sm font-semibold">Gates</h3>
          <ul className="m-0 list-none p-0">
            {s.gates.map((g) => (
              <li key={g.key} className="border-b border-rule-soft py-2 text-[13px]">
                <span className="text-ink">{g.name}</span>{" "}
                <span className="text-mute">{g.passed ? "passed" : "not passed"}</span>
                {Object.keys(g.detail).length > 0 && <span className="block text-ink-2">{detailText(g.detail, s.decimals)}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      {(s.is_countertrend || s.range_mode) && (
        <p className="m-0 mt-3 text-[13px] text-ink-2">
          {s.is_countertrend && "Countertrend trade. "}
          {s.range_mode && "Range mode: the market was moving sideways."}
        </p>
      )}
      {s.explanation && <p className="m-0 mt-4 text-sm text-ink-2">{s.explanation}</p>}
    </section>
  );
}

function Timeline({ s }: { s: SignalDetail }) {
  return (
    <section aria-labelledby="timeline-h" className="border-t border-rule px-5 py-5">
      <h2 id="timeline-h" className="m-0 mb-3 text-base font-semibold">
        Timeline
      </h2>
      <ol className="m-0 list-none p-0">
        {s.events.map((e, i) => (
          <li key={e.id} className="flex gap-3 pb-3">
            <span
              aria-hidden="true"
              className={`mt-1.5 size-2.5 flex-none rounded-full border border-ink ${i === s.events.length - 1 ? "bg-transparent" : "bg-ink"}`}
            />
            <div className="min-w-0 flex-1 text-sm">
              <div className="flex flex-wrap justify-between gap-x-3">
                <span className="font-medium text-ink">{EVENT_NAMES[e.kind] ?? humanize(e.kind)}</span>
                <time dateTime={e.at} className="text-[13px] text-mute">
                  {nyDateTime(new Date(e.at))} NY
                </time>
              </div>
              {e.price && <p className="m-0 text-[13px] text-ink-2">At {e.price}</p>}
              {e.note && e.kind !== "created" && <p className="m-0 text-[13px] text-ink-2">{e.note}</p>}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
