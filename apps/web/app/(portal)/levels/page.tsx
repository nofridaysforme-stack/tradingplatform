import type { Metadata } from "next";
import Link from "next/link";
import { LevelsView } from "@/components/levels-view";
import { listPairs, pairLevels } from "@/lib/levels";
import { requireUser } from "@/lib/session";

export const metadata: Metadata = { title: "Levels · Trading desk" };

export default async function LevelsPage({ searchParams }: PageProps<"/levels">) {
  await requireUser();
  const pairs = await listPairs();
  const { pair } = await searchParams;
  const selected = pairs.find((p) => p.symbol === pair) ?? pairs[0];
  const all = await Promise.all(pairs.map((p) => pairLevels(p)));
  return (
    <main>
      <header className="px-5 pt-6 pb-3.5">
        <h1 className="m-0 text-[22px] font-semibold leading-tight">Levels</h1>
      </header>
      {pairs.length === 0 ? (
        <p className="m-0 border-t border-rule px-5 py-5 text-sm text-ink-2">No pairs are enabled. An admin can add pairs in Settings.</p>
      ) : (
        <>
          {/* Mobile: one pair at a time, chosen with chips. Desktop: every pair. */}
          <nav aria-label="Pairs" className="relative overflow-x-auto px-5 pb-3 lg:hidden">
            <ul className="m-0 flex list-none gap-2 p-0">
              {pairs.map((p) => {
                const on = p.id === selected?.id;
                return (
                  <li key={p.id}>
                    <Link
                      href={`/levels?pair=${encodeURIComponent(p.symbol)}`}
                      aria-current={on ? "page" : undefined}
                      className={`relative inline-flex h-8 items-center whitespace-nowrap rounded-control border px-3 text-[13px] no-underline after:absolute after:-inset-y-1.5 after:inset-x-0 after:content-[''] ${on ? "border-ink bg-ink text-bg" : "border-rule text-ink"}`}
                    >
                      {p.symbol}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="border-t border-rule lg:hidden">
            {all
              .filter((l) => l.instrument === selected?.symbol)
              .map((l) => (
                <LevelsView key={l.instrument} l={l} idPrefix="one" />
              ))}
          </div>
          <div className="hidden border-t border-rule lg:grid lg:grid-cols-2">
            {all.map((l, i) => (
              <div key={l.instrument} className={`border-b border-rule ${i % 2 === 0 ? "border-r" : ""}`}>
                <LevelsView l={l} idPrefix="all" />
              </div>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
