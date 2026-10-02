import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { HoldingForm } from "@/components/holding-form";
import { StockChart } from "@/components/stock-chart";
import { Badge } from "@/components/ui";
import { holdingDefaults } from "@/lib/holdings";
import { money, percent } from "@/lib/format";
import { requireUser } from "@/lib/session";
import { STATUS_NAMES, stockDetail } from "@/lib/stocks";

export const metadata: Metadata = { title: "Stock · Trading desk" };

export default async function StockPage({ params }: PageProps<"/stocks/[ticker]">) {
  await requireUser();
  const ticker = decodeURIComponent((await params).ticker).toUpperCase();
  if (!/^[A-Z][A-Z0-9.\-]{0,9}$/.test(ticker)) notFound();
  const [s, defaults] = await Promise.all([stockDetail(ticker), holdingDefaults()]);
  if (!s) notFound();
  const r = s.latest;
  const t = s.thresholds;
  const lastBar = s.bars.at(-1);
  return (
    <main>
      <nav className="px-5 pt-4">
        <Link href="/stocks" className="inline-flex min-h-11 items-center text-sm text-link">
          <span aria-hidden="true">‹&nbsp;</span>Stocks
        </Link>
      </nav>
      <header className="px-5 pt-1.5 pb-3.5">
        <h1 className="m-0 text-[28px] font-semibold leading-tight tracking-[-0.01em]">{s.ticker}</h1>
        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[13px] text-mute">
          {s.name && <span className="text-ink-2">{s.name}</span>}
          {s.exchange && <span>{s.exchange}</span>}
          {r && <Badge kind="state">{STATUS_NAMES[r.status]}</Badge>}
          {r && <span>Session {r.session}</span>}
        </div>
      </header>

      <section aria-labelledby="chart-h" className="border-t border-rule px-5 py-5">
        <h2 id="chart-h" className="m-0 mb-3 text-base font-semibold">
          Daily chart
        </h2>
        <StockChart ticker={s.ticker} bars={s.bars} />
      </section>

      {r ? (
        <>
          <section aria-labelledby="five-h" className="border-t border-rule px-5 py-5">
            <h2 id="five-h" className="m-0 mb-1 text-base font-semibold">
              Five line chart
            </h2>
            <p className="m-0 mb-3 text-[13px] text-mute">Today&apos;s close against the closes 5, 10, 20, and 50 sessions ago (the N-day closes).</p>
            <FiveLine closes={r.closes} acc={r.acc} apr={r.apr} />
            <p className="m-0 mt-3 text-[13px] text-ink-2">{r.consistent ? "The 5 and 10 day moves agree (consistent)." : "The 5 and 10 day moves do not both point up."}</p>
          </section>

          <section aria-labelledby="checks-h" className="border-t border-rule px-5 py-5">
            <h2 id="checks-h" className="m-0 mb-3 text-base font-semibold">
              Qualification
            </h2>
            <ul className="m-0 list-none p-0 text-sm">
              <Check title="Close near the 52-week high" detail={`Close ${money(r.close)}, 52-week high ${money(r.high_52w)}${t.ratio !== null ? `, needs ${money(r.high_52w * t.ratio)} or more (${percent(t.ratio)} of the high)` : ""}`} />
              <Check title="High at least twice the low" detail={`52-week high ${money(r.high_52w)}, low ${money(r.low_52w)}${t.multiple !== null ? `, needs ${money(r.low_52w * t.multiple)} or more (${t.multiple} times the low)` : ""}`} />
              <Check title="Annual percentage rate" detail={`APR ${percent(r.apr_52w)}${t.minApr !== null ? `, needs ${percent(t.minApr)} or more` : ""}`} />
            </ul>
            <p className="m-0 mt-2 text-[13px] text-mute">Thresholds are the rule versions this screen used.</p>
          </section>
        </>
      ) : (
        <p className="m-0 border-t border-rule px-5 py-5 text-sm text-ink-2">{s.ticker} has not qualified in a stored screen.</p>
      )}

      {s.history.length > 0 && (
        <section aria-labelledby="status-h" className="border-t border-rule px-5 py-5">
          <h2 id="status-h" className="m-0 mb-3 text-base font-semibold">
            Status history
          </h2>
          <ol className="m-0 list-none p-0 text-sm">
            {s.history.map((h) => (
              <li key={h.session} className="flex justify-between gap-3 border-b border-rule-soft py-2">
                <span>{STATUS_NAMES[h.status]}</span>
                <span className="text-mute">From {h.session}</span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section aria-labelledby="add-h" className="border-t border-rule px-5 py-5">
        <h2 id="add-h" className="m-0 mb-3 text-base font-semibold">
          Add to holdings
        </h2>
        <HoldingForm
          idPrefix="add"
          submit="Add to holdings"
          lockTicker
          values={{
            ticker: s.ticker,
            purchasePrice: lastBar ? lastBar.close.toFixed(2) : "",
            purchaseDate: lastBar?.time ?? new Date().toISOString().slice(0, 10),
            ...defaults,
          }}
        />
        <p className="m-0 mt-3 text-[13px] text-mute">
          The portal does not buy or sell. Record a purchase you made with your broker to track its target.{" "}
          <Link href="/holdings" className="text-link underline">
            See holdings
          </Link>
        </p>
      </section>
    </main>
  );
}

function Check({ title, detail }: { title: string; detail: string }) {
  return (
    <li className="border-b border-rule-soft py-2.5">
      <div className="flex justify-between gap-3">
        <span className="font-medium">{title}</span>
        <span className="text-[13px] text-ink">
          <span aria-hidden="true">✓ </span>Passed
        </span>
      </div>
      <p className="m-0 mt-0.5 text-[13px] text-ink-2">{detail}</p>
    </li>
  );
}

function FiveLine({
  closes,
  acc,
  apr,
}: {
  closes: Record<0 | 5 | 10 | 20 | 50, number | null>;
  acc: Record<5 | 10 | 20 | 50, number | null>;
  apr: Record<5 | 10 | 20 | 50, number | null>;
}) {
  const values = Object.values(closes).filter((v): v is number => v !== null);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pos = (v: number) => (hi === lo ? 50 : ((v - lo) / (hi - lo)) * 100);
  const today = closes[0] ?? 0;
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="text-xs text-mute">
          <th scope="col" className="pb-1.5 text-left font-normal">
            Close
          </th>
          <th scope="col" className="pb-1.5 text-right font-normal">
            Price
          </th>
          <th scope="col" className="w-[30%] pb-1.5 font-normal">
            <span className="sr-only">Position between the lowest and highest of the five</span>
          </th>
          <th scope="col" className="pb-1.5 pl-3 text-right font-normal">
            ACC
          </th>
          <th scope="col" className="pb-1.5 pl-3 text-right font-normal">
            APR
          </th>
        </tr>
      </thead>
      <tbody>
        {([0, 5, 10, 20, 50] as const).map((n) => {
          const v = closes[n];
          return (
            <tr key={n} className={`border-t border-rule-soft ${n === 0 ? "font-semibold" : ""}`}>
              <th scope="row" className={`py-2 text-left ${n === 0 ? "font-semibold" : "font-normal text-ink-2"}`}>
                {n === 0 ? "Today" : `${n}-day`}
              </th>
              <td className="py-2 text-right">{money(v)}</td>
              <td className="px-3 py-2" aria-hidden="true">
                <div className="relative h-3">
                  <div className="absolute inset-x-0 top-1/2 border-t border-rule" />
                  {v !== null && (
                    <div
                      className={`absolute top-0 size-3 -translate-x-1/2 rounded-full ${n === 0 ? "bg-ink" : v < today ? "border border-ink bg-bg" : "bg-faint"}`}
                      style={{ left: `${pos(v)}%` }}
                    />
                  )}
                </div>
              </td>
              <td className="py-2 pl-3 text-right">{n === 0 ? "" : percent(acc[n])}</td>
              <td className="py-2 pl-3 text-right">{n === 0 ? "" : percent(apr[n])}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
