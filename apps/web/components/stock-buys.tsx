import Link from "next/link";
import { Badge, ProvisionalBadge } from "@/components/ui";
import { money, signedPercent } from "@/lib/format";
import { EVENT_NAMES, INDICATOR_NAMES, INDICATORS, patternName } from "@/lib/stock-names";
import { EXIT_NAMES, type StockBuy } from "@/lib/stocks";
import type { Evidence } from "@/lib/db/schema";

/** The indicators that voted, in words and in the spec 08 order: "Price and candle (engulfing), MACD crossover". */
export function votedText(e: Evidence | null): string {
  if (!e) return "";
  return INDICATORS.filter((k) => e[k]?.fired)
    .map((k) => `${INDICATOR_NAMES[k]}${e[k]!.patterns?.length ? ` (${e[k]!.patterns!.map(patternName).join(", ")})` : ""}`)
    .join(", ");
}

/** Buys from the stock system (spec 08): the plan, where the stop is now, and the exit. */
export function StockBuys({ buys, showTicker = true, events = false }: { buys: StockBuy[]; showTicker?: boolean; events?: boolean }) {
  return (
    <ul className="m-0 list-none p-0">
      {buys.map((b) => {
        const open = b.state === "open";
        const result = open ? (b.lastClose === null ? null : (b.lastClose - b.entry) / b.entry) : b.resultPct;
        const count = Object.values(b.votes).filter((v) => v.fired).length;
        return (
          <li key={b.id} className="border-b border-rule-soft px-5 py-3.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <span className="flex flex-wrap items-baseline gap-2">
                <span className="text-sm font-semibold text-long">
                  <span aria-hidden="true">▲</span> Buy
                </span>
                {showTicker && (
                  <Link href={`/stocks/${encodeURIComponent(b.ticker)}`} className="text-[17px] font-semibold text-ink no-underline">
                    {b.ticker}
                  </Link>
                )}
                <span className="text-[13px] text-mute">
                  {b.buySession} at {money(b.entry)}
                </span>
                {b.hasProvisional && <ProvisionalBadge />}
              </span>
              <span className="text-sm">
                {open ? (
                  <Badge kind="state">Open</Badge>
                ) : (
                  <span>
                    <Badge kind="state">{EXIT_NAMES[b.state as Exclude<StockBuy["state"], "open">]}</Badge>{" "}
                    <span className="text-mute">{b.exitSession}</span>
                  </span>
                )}
              </span>
            </div>
            <dl className="m-0 mt-2.5 grid grid-cols-2 gap-x-4 gap-y-2 text-right sm:grid-cols-5">
              <Cell label={open ? "Stop now" : "Exit"} value={open ? money(b.stopNow) : money(b.exitPrice)} hint={open ? (b.trailingActive ? "Trailing" : "Fixed 5%") : undefined} strong />
              <Cell label="Highest close" value={money(b.highestClose)} />
              <Cell label={`Projection (${b.projectionPct}%)`} value={money(b.projection)} hint={b.projectionSession ? `Reached ${b.projectionSession}` : `In ${b.horizonSessions} sessions`} />
              <Cell label={open ? "Last close" : "Result"} value={open ? money(b.lastClose) : signedPercent(result)} strong={!open} />
              <Cell label={open ? "So far" : "Votes"} value={open ? signedPercent(result) : `${count} of 5`} />
            </dl>
            <p className="m-0 mt-2 text-[13px] text-ink-2">
              {count} of 5 voted to buy: {votedText(b.votes)}.
              {b.state === "sold" && b.exitVotes && <> Sold on: {votedText(b.exitVotes)}.</>}
            </p>
            {events && b.events.length > 0 && (
              <ol className="m-0 mt-2 list-none p-0 text-[13px] text-ink-2">
                {b.events.map((e) => (
                  <li key={e.kind} className="flex justify-between gap-3 border-t border-rule-faint py-1.5">
                    <span>{EVENT_NAMES[e.kind] ?? e.kind}</span>
                    <span className="text-mute">
                      {e.session}
                      {e.price !== null && ` at ${money(e.price)}`}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Cell({ label, value, hint, strong = false }: { label: string; value: string; hint?: string; strong?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-mute">{label}</dt>
      <dd className={`m-0 text-[15px] ${strong ? "font-semibold" : ""}`}>
        {value || "None"}
        {hint && <span className="block text-xs font-normal text-mute">{hint}</span>}
      </dd>
    </div>
  );
}
