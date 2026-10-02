import { asc, eq, sql as dsql } from "drizzle-orm";
import type { Metadata } from "next";
import Link from "next/link";
import { db } from "@/lib/db";
import { instruments } from "@/lib/db/schema";
import { requireAdmin } from "@/lib/session";
import { AddPairForm, PairRow } from "./forms";

export const metadata: Metadata = { title: "Pairs · Trading desk" };

export default async function PairsPage() {
  await requireAdmin();
  const pairs = await db
    .select({
      id: instruments.id,
      symbol: instruments.symbol,
      pipSize: instruments.pipSize,
      decimals: instruments.displayDecimals,
      enabled: instruments.enabled,
      sortOrder: instruments.sortOrder,
      hasHistory: dsql<boolean>`exists (select 1 from candles c where c.instrument_id = ${instruments.id} and c.granularity = 'D')`,
    })
    .from(instruments)
    .where(eq(instruments.assetClass, "forex"))
    .orderBy(asc(instruments.sortOrder), asc(instruments.symbol));
  return (
    <main>
      <nav className="px-5 pt-4">
        <Link href="/settings" className="inline-flex min-h-11 items-center text-sm text-link">
          <span aria-hidden="true">‹&nbsp;</span>Settings
        </Link>
      </nav>
      <header className="px-5 pt-1.5 pb-3.5">
        <h1 className="m-0 text-[22px] font-semibold leading-tight">Pairs</h1>
        <p className="m-0 mt-1 max-w-[62ch] text-[13px] text-mute">
          The forex pairs the scanner watches. A pair that is off is not scanned and its alerts stop. Which strategies scan which pairs is set under Rules.
        </p>
      </header>
      <section aria-labelledby="pairs-h" className="border-t border-rule">
        <h2 id="pairs-h" className="sr-only">
          Pairs
        </h2>
        <ul className="m-0 list-none p-0">
          {pairs.map((p) => (
            <li key={p.id} className="border-b border-rule-soft px-5 py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="text-[17px] font-semibold">{p.symbol}</span>
                <span className="text-[13px] text-mute">
                  Pip {Number(p.pipSize)} · {p.decimals} decimals · {p.hasHistory ? "History loaded" : "History loading"}
                </span>
              </div>
              <PairRow id={p.id} symbol={p.symbol} enabled={p.enabled} sortOrder={p.sortOrder} />
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="add-h" className="border-t border-rule px-5 py-5">
        <h2 id="add-h" className="m-0 mb-3 text-base font-semibold">
          Add pair
        </h2>
        <AddPairForm />
      </section>
    </main>
  );
}
