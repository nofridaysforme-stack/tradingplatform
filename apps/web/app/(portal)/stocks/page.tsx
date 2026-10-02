import type { Metadata } from "next";
import Link from "next/link";
import { Badge, Button } from "@/components/ui";
import { money, percent } from "@/lib/format";
import { requireUser } from "@/lib/session";
import { parseResultsQuery, results, resultsHref, sessions, STATUS_NAMES, STATUSES, type SortKey } from "@/lib/stocks";

export const metadata: Metadata = { title: "Stocks · Trading desk" };

const COLUMNS: { key: SortKey; label: string; group?: string }[] = [
  { key: "ticker", label: "Ticker" },
  { key: "status", label: "Status" },
  { key: "close", label: "Close" },
  { key: "high", label: "52-week high" },
  { key: "low", label: "52-week low" },
  { key: "apr", label: "52-week APR" },
  { key: "acc5", label: "5", group: "ACC" },
  { key: "acc10", label: "10", group: "ACC" },
  { key: "acc20", label: "20", group: "ACC" },
  { key: "acc50", label: "50", group: "ACC" },
  { key: "apr5", label: "5", group: "APR" },
  { key: "apr10", label: "10", group: "APR" },
  { key: "apr20", label: "20", group: "APR" },
  { key: "apr50", label: "50", group: "APR" },
];

export default async function StocksPage({ searchParams }: PageProps<"/stocks">) {
  await requireUser();
  const q = parseResultsQuery(await searchParams);
  const [data, sessionList] = await Promise.all([results(q), sessions()]);
  return (
    <main>
      <header className="px-5 pt-6 pb-3.5">
        <h1 className="m-0 text-[22px] font-semibold leading-tight">Stocks</h1>
        <p className="m-0 mt-1 text-[13px] text-mute">
          {data.session ? <>Screen for the {data.session} session · {data.total} stocks</> : "No screen has run yet. The scanner screens US stocks each weekday evening."}
        </p>
      </header>

      <form method="get" action="/stocks" aria-label="Filters" className="flex flex-wrap items-end gap-3 border-t border-rule px-5 py-4">
        <Choice id="session" label="Session" value={data.session ?? ""} options={sessionList.map((s) => [s, s])} />
        <Choice id="status" label="Status" value={q.status ?? ""} options={[["", "All"], ...STATUSES.map((s) => [s, STATUS_NAMES[s]] as [string, string])]} />
        <div className="flex flex-col gap-1.5">
          <label htmlFor="q" className="text-xs text-mute">
            Search
          </label>
          <input id="q" name="q" type="search" defaultValue={q.q ?? ""} placeholder="Ticker or name" className="h-11 w-44 rounded-control border border-rule bg-input px-2.5 text-sm text-ink" />
        </div>
        {q.sort && <input type="hidden" name="sort" value={q.sort} />}
        {q.dir && <input type="hidden" name="dir" value={q.dir} />}
        <Button kind="secondary" type="submit">
          Apply filters
        </Button>
      </form>

      {data.rows.length === 0 ? (
        <p className="m-0 border-t border-rule px-5 py-5 text-sm text-ink-2">{data.session ? "No stocks match these filters." : "Results appear here after the first evening screen."}</p>
      ) : (
        <div className="relative overflow-x-auto border-t border-rule">
          <table className="w-full min-w-[1040px] border-collapse font-condensed text-sm">
            <caption className="sr-only">
              Screen results, sorted by {COLUMNS.find((c) => c.key === data.sort)?.group ?? ""} {COLUMNS.find((c) => c.key === data.sort)?.label} {data.dir === "asc" ? "ascending" : "descending"}
            </caption>
            <thead className="sticky top-0 bg-bg">
              <tr className="text-xs text-mute">
                {COLUMNS.map((c, i) => {
                  const on = data.sort === c.key;
                  const nextDir = on && data.dir === "desc" ? "asc" : on ? "desc" : c.key === "ticker" ? "asc" : "desc";
                  return (
                    <th
                      key={c.key}
                      scope="col"
                      aria-sort={on ? (data.dir === "asc" ? "ascending" : "descending") : undefined}
                      className={`border-b border-rule px-2 py-2 font-normal first:pl-5 last:pr-5 ${i >= 2 ? "text-right" : "text-left"}`}
                    >
                      <Link href={resultsHref(q, { sort: c.key, dir: nextDir, page: 1 })} className={`no-underline ${on ? "font-semibold text-ink" : "text-mute"}`}>
                        {c.group && <span className="sr-only">{c.group} </span>}
                        {c.group ? `${c.group} ${c.label}` : c.label}
                        {on && <span aria-hidden="true">{data.dir === "asc" ? " ↑" : " ↓"}</span>}
                      </Link>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.ticker} className="border-b border-rule-soft">
                  <td className="px-2 py-2 pl-5">
                    <Link href={`/stocks/${encodeURIComponent(r.ticker)}`} className="font-semibold text-link">
                      {r.ticker}
                    </Link>
                    {r.name && <span className="block max-w-[180px] truncate text-xs text-mute">{r.name}</span>}
                  </td>
                  <td className="px-2 py-2">
                    <Badge kind="state">{STATUS_NAMES[r.status]}</Badge>
                    {r.consistent && <span className="block text-xs text-mute">Consistent</span>}
                  </td>
                  <td className="px-2 py-2 text-right">{money(r.close)}</td>
                  <td className="px-2 py-2 text-right">{money(r.high_52w)}</td>
                  <td className="px-2 py-2 text-right">{money(r.low_52w)}</td>
                  <td className="px-2 py-2 text-right">{percent(r.apr_52w)}</td>
                  {([5, 10, 20, 50] as const).map((n) => (
                    <td key={`acc${n}`} className="px-2 py-2 text-right">
                      {percent(r.acc[n])}
                    </td>
                  ))}
                  {([5, 10, 20, 50] as const).map((n) => (
                    <td key={`apr${n}`} className="px-2 py-2 text-right last:pr-5">
                      {percent(r.apr[n])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.pages > 1 && (
        <nav aria-label="Pages" className="flex items-center justify-between gap-3 px-5 py-4 text-sm">
          {data.page > 1 ? (
            <Link href={resultsHref(q, { page: data.page - 1 })} className="inline-flex min-h-11 items-center text-link">
              Previous
            </Link>
          ) : (
            <span />
          )}
          <span className="text-mute">
            Page {data.page} of {data.pages}
          </span>
          {data.page < data.pages ? (
            <Link href={resultsHref(q, { page: data.page + 1 })} className="inline-flex min-h-11 items-center text-link">
              Next
            </Link>
          ) : (
            <span />
          )}
        </nav>
      )}
      <p className="m-0 border-t border-rule px-5 py-4 text-[13px] text-mute">
        ACC is the change since the close N sessions ago; APR annualizes it over the trader year set in the five-line rule (260 sessions by default).
      </p>
    </main>
  );
}

function Choice({ id, label, value, options }: { id: string; label: string; value: string; options: [string, string][] }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs text-mute">
        {label}
      </label>
      <select id={id} name={id} defaultValue={value} className="h-11 rounded-control border border-rule bg-input px-2.5 text-sm text-ink">
        {options.map(([v, l]) => (
          <option key={v || "all"} value={v}>
            {l}
          </option>
        ))}
      </select>
    </div>
  );
}
