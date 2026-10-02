import { nyTime } from "@/lib/format";
import {
  LADDER_STEPS,
  PIVOT_KEYS,
  type Ladder,
  type PairLevels,
} from "@/lib/levels";

const fmt = (v: number | undefined, d: number) =>
  v === undefined ? "" : v.toFixed(d);

/** One pair's levels (handoff 1e): floor pivots, PDH and PDL, and the Fibonacci Pivot ladder
 *  with spec 07's level names. */
export function LevelsView({
  l,
  idPrefix,
  headingLevel = 2,
}: {
  l: PairLevels;
  idPrefix: string;
  headingLevel?: 2 | 3;
}) {
  const H = headingLevel === 2 ? "h2" : "h3";
  const sub = headingLevel === 2 ? "h3" : "h4";
  const id = `${idPrefix}-${l.instrument.replace("/", "-").toLowerCase()}`;
  const day = l.trading_day;
  if (!day) {
    return (
      <section aria-labelledby={`${id}-h`} className="px-5 py-5">
        <H id={`${id}-h`} className="m-0 text-[17px] font-semibold">
          {l.instrument}
        </H>
        <p className="m-0 mt-2 text-sm text-ink-2">
          No levels yet. They are computed at the 17:00 New York day roll.
        </p>
      </section>
    );
  }
  return (
    <section aria-labelledby={`${id}-h`} className="px-5 py-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <H id={`${id}-h`} className="m-0 text-[17px] font-semibold">
          {l.instrument}
        </H>
        <p className="m-0 text-[13px] text-mute">
          Trading day {day}
          {l.last_price !== null && l.last_price_at && (
            <>
              {" "}
              · Now{" "}
              <span className="text-ink">
                {l.last_price.toFixed(l.decimals)}
              </span>{" "}
              at {nyTime(new Date(l.last_price_at))} NY
            </>
          )}
        </p>
      </div>

      {(l.daily || l.weekly || l.monthly) && (
        <table className="mt-3 w-full border-collapse text-sm">
          <caption className="sr-only">Floor pivots for {l.instrument}</caption>
          <thead>
            <tr className="text-xs text-mute">
              <th scope="col" className="pb-1.5 text-left font-normal">
                Floor pivots
              </th>
              <th scope="col" className="pb-1.5 text-right font-normal">
                Daily
              </th>
              <th scope="col" className="pb-1.5 text-right font-normal">
                Weekly
              </th>
              <th scope="col" className="pb-1.5 text-right font-normal">
                Monthly
              </th>
            </tr>
          </thead>
          <tbody>
            {PIVOT_KEYS.map((k) => (
              <tr
                key={k}
                className={`border-t border-rule-soft ${k === "P" ? "font-semibold" : ""}`}
              >
                <th
                  scope="row"
                  className={`py-1.5 text-left ${k === "P" ? "font-semibold" : "font-normal text-ink-2"}`}
                >
                  {k}
                </th>
                <td className="py-1.5 text-right">
                  {fmt(l.daily?.[k], l.decimals)}
                </td>
                <td className="py-1.5 text-right">
                  {fmt(l.weekly?.[k], l.decimals)}
                </td>
                <td className="py-1.5 text-right">
                  {fmt(l.monthly?.[k], l.decimals)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {l.prev_day && (
        <dl className="m-0 mt-3 flex gap-6 border-t border-rule pt-3 text-sm">
          <div className="flex gap-2">
            <dt className="text-ink-2">PDH</dt>
            <dd className="m-0">{fmt(l.prev_day.PDH, l.decimals)}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-ink-2">PDL</dt>
            <dd className="m-0">{fmt(l.prev_day.PDL, l.decimals)}</dd>
          </div>
        </dl>
      )}

      {l.fib_pivot && (
        <LadderView
          ladder={l.fib_pivot}
          decimals={l.decimals}
          now={l.last_price}
          heading={sub}
        />
      )}
    </section>
  );
}

type Rung = { label: string; price: number; pivot?: boolean; now?: boolean };

export function ladderRungs(ladder: Ladder, now: number | null): Rung[] {
  const rungs: Rung[] = [
    ...LADDER_STEPS.flatMap(([k, label]) =>
      ladder.up[k] === undefined
        ? []
        : [{ label: `${label} up`, price: ladder.up[k] }],
    ),
    { label: "Pivot", price: ladder.pivot, pivot: true },
    ...[...LADDER_STEPS]
      .reverse()
      .flatMap(([k, label]) =>
        ladder.down[k] === undefined
          ? []
          : [{ label: `${label} down`, price: ladder.down[k] }],
      ),
  ];
  if (now !== null) {
    const at = rungs.findIndex((r) => now >= r.price);
    rungs.splice(at === -1 ? rungs.length : at, 0, {
      label: "Now",
      price: now,
      now: true,
    });
  }
  return rungs;
}

function LadderView({
  ladder,
  decimals,
  now,
  heading: Sub,
}: {
  ladder: Ladder;
  decimals: number;
  now: number | null;
  heading: "h3" | "h4";
}) {
  return (
    <div className="mt-4 border-t border-rule pt-3">
      <Sub className="m-0 text-sm font-semibold">Fibonacci Pivot</Sub>
      {(ladder.range !== null || ladder.fib !== null) && (
        <p className="m-0 mt-0.5 text-[13px] text-mute">
          {ladder.range !== null && <>Range {ladder.range} pips</>}
          {ladder.range !== null && ladder.fib !== null && " · "}
          {ladder.fib !== null && <>Fibonacci {ladder.fib}</>}
        </p>
      )}
      <ol className="m-0 mt-2 list-none p-0">
        {ladderRungs(ladder, now).map((r) =>
          r.now ? (
            <li
              key="now"
              className="flex items-center gap-2 py-1 text-[13px] font-semibold text-long"
            >
              <span
                aria-hidden="true"
                className="size-2 rounded-full bg-long"
              />
              <span className="flex-1">Now</span>
              <span>{r.price.toFixed(decimals)}</span>
            </li>
          ) : (
            <li key={r.label} className="flex items-center gap-3 py-1 text-sm">
              <span
                className={`flex-1 ${r.pivot ? "font-semibold text-ink" : "text-ink-2"}`}
              >
                {r.label}
              </span>
              <span
                aria-hidden="true"
                className={`h-0 w-10 border-t ${r.pivot ? "border-[1.5px] border-ink" : "border-rule"}`}
              />
              <span
                className={`w-20 text-right ${r.pivot ? "font-semibold" : ""}`}
              >
                {r.price.toFixed(decimals)}
              </span>
            </li>
          ),
        )}
      </ol>
    </div>
  );
}
