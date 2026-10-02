import type { Metadata } from "next";
import Link from "next/link";
import { HoldingForm } from "@/components/holding-form";
import { money, percent } from "@/lib/format";
import { holdingDefaults, listHoldings, type HoldingView } from "@/lib/holdings";
import { requireUser } from "@/lib/session";
import { CloseHolding } from "./close-button";

export const metadata: Metadata = { title: "Holdings · Trading desk" };

export default async function HoldingsPage() {
  const user = await requireUser();
  const [all, defaults] = await Promise.all([listHoldings(user.id), holdingDefaults()]);
  const open = all.filter((h) => !h.closed);
  const closed = all.filter((h) => h.closed);
  return (
    <main>
      <header className="px-5 pt-6 pb-3.5">
        <h1 className="m-0 text-[22px] font-semibold leading-tight">Holdings</h1>
        <p className="m-0 mt-1 max-w-[62ch] text-[13px] text-mute">
          Your own purchases and their sales targets. Only you see your holdings. The portal never buys or sells.
        </p>
      </header>

      <section aria-labelledby="open-h" className="border-t border-rule">
        <h2 id="open-h" className="m-0 px-5 pt-4 text-base font-semibold">
          Open
        </h2>
        {open.length === 0 ? (
          <p className="m-0 px-5 py-4 text-sm text-ink-2">No open holdings. Add one below or from a stock&apos;s page.</p>
        ) : (
          <ul className="m-0 list-none p-0">
            {open.map((h) => (
              <HoldingRow key={h.id} h={h} />
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="add-h" className="border-t border-rule px-5 py-5">
        <h2 id="add-h" className="m-0 mb-3 text-base font-semibold">
          Add a holding
        </h2>
        <HoldingForm
          idPrefix="new"
          submit="Add holding"
          values={{ ticker: "", purchasePrice: "", purchaseDate: new Date().toISOString().slice(0, 10), ...defaults }}
        />
      </section>

      {closed.length > 0 && (
        <section aria-labelledby="closed-h" className="border-t border-rule">
          <h2 id="closed-h" className="m-0 px-5 pt-4 text-base font-semibold">
            Closed
          </h2>
          <ul className="m-0 list-none p-0">
            {closed.map((h) => (
              <li key={h.id} className="flex justify-between gap-3 border-b border-rule-soft px-5 py-3 text-sm">
                <span>
                  <strong className="font-semibold">{h.ticker}</strong> bought {h.purchaseDate} at {money(h.purchasePrice)}
                </span>
                <span className="text-mute">Target {money(h.plan.target)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

function HoldingRow({ h }: { h: HoldingView }) {
  const c = h.check;
  const progress = c ? Math.max(0, Math.min(1, c.progress)) : 0;
  return (
    <li className="border-b border-rule-soft px-5 py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <Link href={`/stocks/${encodeURIComponent(h.ticker)}`} className="text-[17px] font-semibold text-ink no-underline">
          {h.ticker}
        </Link>
        <span className="text-[13px] text-mute">
          Bought {h.purchaseDate} at {money(h.purchasePrice)} · {h.expectedProfitPct}% expected
        </span>
      </div>
      <dl className="m-0 mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-right sm:grid-cols-5">
        <Cell label="Sales target" value={money(h.plan.target)} strong />
        <Cell label="Total earnings" value={money(h.plan.earnings)} />
        <Cell label="Daily target" value={h.plan.daily.toFixed(3)} />
        <Cell label="Weekly target" value={h.plan.weekly.toFixed(3)} />
        <Cell label="Last close" value={h.lastClose === null ? "No bars yet" : money(h.lastClose)} />
      </dl>
      {c && (
        <div className="mt-3">
          <div
            role="meter"
            aria-label={`Progress toward the ${h.ticker} target`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress * 100)}
            className="relative h-2 bg-rule-faint"
          >
            <div className="absolute inset-y-0 left-0 bg-ink" style={{ width: `${progress * 100}%` }} />
          </div>
          <p className="m-0 mt-1.5 flex flex-wrap justify-between gap-x-3 text-[13px] text-ink-2">
            <span>
              {percent(c.progress)} of the planned earnings
              {c.targetReached && " · Target reached"}
              {c.timeElapsed && " · Horizon passed without the target"}
            </span>
            <span>
              {c.sessionsElapsed} of {h.horizonSessions} sessions
            </span>
          </p>
        </div>
      )}
      {h.notes && <p className="m-0 mt-2 text-[13px] text-ink-2">{h.notes}</p>}
      <div className="mt-3 flex flex-wrap items-start gap-3">
        <details className="flex-1">
          <summary className="inline-flex min-h-11 cursor-pointer items-center text-sm text-link">Edit holding</summary>
          <div className="pt-2">
            <HoldingForm
              idPrefix={`edit-${h.id}`}
              submit="Save changes"
              values={{
                id: h.id,
                ticker: h.ticker,
                purchasePrice: String(h.purchasePrice),
                purchaseDate: h.purchaseDate,
                expectedProfitPct: h.expectedProfitPct,
                horizonSessions: h.horizonSessions,
                notes: h.notes,
              }}
            />
          </div>
        </details>
        <CloseHolding id={h.id} ticker={h.ticker} />
      </div>
    </li>
  );
}

function Cell({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-mute">{label}</dt>
      <dd className={`m-0 text-[15px] ${strong ? "font-semibold" : ""}`}>{value}</dd>
    </div>
  );
}
