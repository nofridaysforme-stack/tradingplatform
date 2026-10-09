import { asc, eq } from "drizzle-orm";
import type { Metadata } from "next";
import Link from "next/link";
import { requireForex } from "@/lib/app-settings";
import { db } from "@/lib/db";
import { brokerSpreads, brokers, instruments, users } from "@/lib/db/schema";
import { requireAdmin } from "@/lib/session";
import { BrokerForm, DeleteBroker, type BrokerValues } from "./broker-form";

export const metadata: Metadata = { title: "Brokers · Trading desk" };

export default async function BrokersPage() {
  await requireAdmin();
  await requireForex();
  const [list, spreads, pairs, usage] = await Promise.all([
    db.select().from(brokers).orderBy(asc(brokers.name)),
    db.select().from(brokerSpreads),
    db
      .select({ id: instruments.id, symbol: instruments.symbol })
      .from(instruments)
      .where(eq(instruments.enabled, true))
      .orderBy(asc(instruments.sortOrder), asc(instruments.symbol)),
    db.select({ brokerId: users.activeBrokerId }).from(users),
  ]);
  const values = (b: (typeof list)[number]): BrokerValues => ({
    id: b.id,
    name: b.name,
    template: b.platformUrlTemplate ?? "",
    notes: b.notes ?? "",
    spreads: Object.fromEntries(
      spreads
        .filter((s) => s.brokerId === b.id)
        .map((s) => [s.instrumentId, { pips: String(Number(s.typicalSpreadPips)), symbol: s.symbolOverride ?? "" }]),
    ),
  });
  return (
    <main>
      <nav className="px-5 pt-4">
        <Link href="/settings" className="inline-flex min-h-11 items-center text-sm text-link">
          <span aria-hidden="true">‹&nbsp;</span>Settings
        </Link>
      </nav>
      <header className="px-5 pt-1.5 pb-3.5">
        <h1 className="m-0 text-[22px] font-semibold leading-tight">Brokers</h1>
        <p className="m-0 mt-1 max-w-[62ch] text-[13px] text-mute">
          Each owner picks a broker in Settings. Their signal prices shift by half its typical spread, and &quot;Open in&quot; uses its chart link. The portal never places trades.
        </p>
      </header>

      <section aria-labelledby="list-h" className="border-t border-rule">
        <h2 id="list-h" className="sr-only">
          Brokers
        </h2>
        {list.length === 0 ? (
          <p className="m-0 px-5 py-4 text-sm text-ink-2">No brokers yet.</p>
        ) : (
          <ul className="m-0 list-none p-0">
            {list.map((b) => {
              const v = values(b);
              const n = Object.keys(v.spreads).length;
              const owners = usage.filter((u) => u.brokerId === b.id).length;
              return (
                <li key={b.id} className="border-b border-rule-soft px-5 py-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                    <span className="text-[17px] font-semibold">{b.name}</span>
                    <span className="text-[13px] text-mute">
                      Spreads for {n} pair{n === 1 ? "" : "s"} · Used by {owners} owner{owners === 1 ? "" : "s"}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-start gap-3">
                    <details className="min-w-0 flex-1">
                      <summary className="inline-flex min-h-11 cursor-pointer items-center text-sm text-link">Edit broker</summary>
                      <div className="pt-2">
                        <BrokerForm values={v} pairs={pairs} idPrefix={`b-${b.id}`} />
                      </div>
                    </details>
                    <DeleteBroker id={b.id} name={b.name} />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section aria-labelledby="add-h" className="border-t border-rule px-5 py-5">
        <h2 id="add-h" className="m-0 mb-3 text-base font-semibold">
          Add broker
        </h2>
        <BrokerForm values={{ name: "", template: "", notes: "", spreads: {} }} pairs={pairs} idPrefix="new" />
      </section>
    </main>
  );
}
