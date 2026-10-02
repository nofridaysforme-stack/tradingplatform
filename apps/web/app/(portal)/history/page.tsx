import type { Metadata } from "next";
import Link from "next/link";
import { CumulativeChart } from "@/components/cumulative-chart";
import { Button, DirectionMarker, ProvisionalBadge } from "@/components/ui";
import { pips, ratio, STATE_NAMES, STRATEGY_NAMES } from "@/lib/format";
import { filterQuery, historyPage, instrumentSymbols, OUTCOMES, parseFilter, type HistoryFilter } from "@/lib/history";
import { requireUser } from "@/lib/session";

export const metadata: Metadata = { title: "History · Trading desk" };

export default async function HistoryPage({ searchParams }: PageProps<"/history">) {
  await requireUser();
  const filter = parseFilter(await searchParams);
  const [data, symbols] = await Promise.all([historyPage(filter), instrumentSymbols()]);
  const s = data.summary;
  return (
    <main>
      <header className="flex flex-wrap items-end justify-between gap-3 px-5 pt-6 pb-3.5">
        <h1 className="m-0 text-[22px] font-semibold leading-tight">History</h1>
        <a
          href={`/api/history/export.csv${filterQuery(filter)}`}
          className="inline-flex h-11 items-center rounded-control border border-rule px-4 text-sm font-medium text-ink no-underline"
          download
        >
          Export CSV
        </a>
      </header>

      <Filters filter={filter} symbols={symbols} />

      <section aria-label="Summary" className="border-t border-rule px-5 py-4">
        <dl className="m-0 flex flex-wrap gap-x-0 gap-y-3">
          <Metric label="Trades" value={String(s.trades)} />
          <Metric label="Win rate" value={s.trades ? `${Math.round(s.winRate * 100)}%` : "None"} />
          <Metric label="Net" value={pips(s.netPips)} unit="pips" />
          <Metric label="Expectancy" value={pips(s.expectancy)} unit="pips" />
          <Metric label="Profit factor" value={s.profitFactor === null ? "None" : s.profitFactor.toFixed(2)} last />
        </dl>
        <p className="m-0 mt-2 text-[13px] text-mute">
          Reference prices, before broker spreads. Invalidated signals are left out.
        </p>
      </section>

      <section aria-labelledby="curve-h" className="border-t border-rule px-5 py-4">
        <h2 id="curve-h" className="m-0 mb-2 text-sm font-semibold">
          Cumulative pips
        </h2>
        <CumulativeChart points={data.curve} />
      </section>

      <section aria-labelledby="table-h" className="border-t border-rule">
        <h2 id="table-h" className="sr-only">
          Closed signals
        </h2>
        {data.total === 0 ? (
          <p className="m-0 px-5 py-5 text-sm text-ink-2">No closed signals match these filters.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] border-collapse font-condensed text-sm">
              <thead className="sticky top-0 bg-bg">
                <tr className="text-xs text-mute">
                  {["Date", "Strategy", "Pair", "Direction", "Outcome", "Pips", "R:R", "Rules"].map((h, i) => (
                    <th key={h} scope="col" className={`border-b border-rule px-2 py-2 font-normal first:pl-5 last:pr-5 ${i >= 5 && i <= 6 ? "text-right" : "text-left"}`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.id} className="border-b border-rule-soft">
                    <td className="px-2 py-2 pl-5">
                      <Link href={`/signals/${r.id}`} className="text-link">
                        {r.trading_day}
                      </Link>
                    </td>
                    <td className="px-2 py-2">{STRATEGY_NAMES[r.strategy]}</td>
                    <td className="px-2 py-2">{r.instrument}</td>
                    <td className="px-2 py-2">
                      <DirectionMarker direction={r.direction} />
                    </td>
                    <td className="px-2 py-2">{STATE_NAMES[r.outcome]}</td>
                    <td className="px-2 py-2 text-right">{r.result_pips === null ? "" : pips(r.result_pips)}</td>
                    <td className="px-2 py-2 text-right">{ratio(r.reward_risk)}</td>
                    <td className="px-2 py-2 pr-5">
                      <details>
                        <summary className="cursor-pointer text-ink-2">
                          {Object.keys(r.version_set).length} rules
                        </summary>
                        <ul className="m-0 mt-1 list-none p-0 text-xs text-ink-2">
                          {Object.entries(r.version_set).map(([k, v]) => (
                            <li key={k}>
                              {k} v{v}
                            </li>
                          ))}
                        </ul>
                      </details>
                      {r.has_provisional && (
                        <span className="mt-1 block">
                          <ProvisionalBadge />
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data.pages > 1 && (
          <nav aria-label="Pages" className="flex items-center justify-between gap-3 px-5 py-4 text-sm">
            {data.page > 1 ? (
              <Link href={`/history${filterQuery(filter, data.page - 1)}`} className="inline-flex min-h-11 items-center text-link">
                Newer
              </Link>
            ) : (
              <span />
            )}
            <span className="text-mute">
              Page {data.page} of {data.pages} · {data.total} signals
            </span>
            {data.page < data.pages ? (
              <Link href={`/history${filterQuery(filter, data.page + 1)}`} className="inline-flex min-h-11 items-center text-link">
                Older
              </Link>
            ) : (
              <span />
            )}
          </nav>
        )}
      </section>
    </main>
  );
}

function Metric({ label, value, unit, last = false }: { label: string; value: string; unit?: string; last?: boolean }) {
  return (
    <div className={`pr-5 ${last ? "" : "mr-5 border-r border-rule"}`}>
      <dt className="text-xs text-mute">{label}</dt>
      <dd className="m-0 text-[22px] font-semibold leading-tight">
        {value}
        {unit && <span className="ml-1 text-xs font-normal text-mute">{unit}</span>}
      </dd>
    </div>
  );
}

function Select({ id, label, value, options }: { id: string; label: string; value?: string; options: [string, string][] }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs text-mute">
        {label}
      </label>
      <select
        id={id}
        name={id}
        defaultValue={value ?? ""}
        className="h-11 rounded-control border border-rule bg-input px-2.5 text-sm text-ink"
      >
        <option value="">All</option>
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </div>
  );
}

function Filters({ filter, symbols }: { filter: HistoryFilter; symbols: string[] }) {
  return (
    <form method="get" action="/history" aria-label="Filters" className="flex flex-wrap items-end gap-3 border-t border-rule px-5 py-4">
      {(["from", "to"] as const).map((k) => (
        <div key={k} className="flex flex-col gap-1.5">
          <label htmlFor={k} className="text-xs text-mute">
            {k === "from" ? "From" : "To"}
          </label>
          <input
            id={k}
            name={k}
            type="date"
            defaultValue={filter[k] ?? ""}
            className="h-11 rounded-control border border-rule bg-input px-2.5 text-sm text-ink"
          />
        </div>
      ))}
      <Select id="strategy" label="Strategy" value={filter.strategy} options={Object.entries(STRATEGY_NAMES)} />
      <Select id="instrument" label="Pair" value={filter.instrument} options={symbols.map((x) => [x, x])} />
      <Select id="direction" label="Direction" value={filter.direction} options={[["long", "Long"], ["short", "Short"]]} />
      <Select id="outcome" label="Outcome" value={filter.outcome} options={OUTCOMES.map((o) => [o, STATE_NAMES[o]])} />
      <Select id="provisional" label="Provisional" value={filter.provisional} options={[["yes", "With provisional rules"], ["no", "Approved rules only"]]} />
      <div className="flex gap-2">
        <Button kind="secondary" type="submit">
          Apply filters
        </Button>
        <Link href="/history" className="inline-flex h-11 items-center px-2 text-sm text-link">
          Clear
        </Link>
      </div>
    </form>
  );
}
