import Link from "next/link";
import { LadderMark, IndicatorRing, ringStates } from "@/components/ring";
import { Badge, DirectionMarker, ProvisionalBadge } from "@/components/ui";
import { age, ratio, STATE_NAMES, STRATEGY_NAMES } from "@/lib/format";
import type { SignalListItem } from "@/lib/signals";

/** Dashboard row (handoff 1b): direction, instrument, meta, badges, ring or ladder, and a
 *  4-column price grid. Prices are the broker-adjusted ones when a broker is chosen. */
export function SignalRow({ s, now }: { s: SignalListItem; now: Date }) {
  const p = s.adjusted ?? s.reference;
  const fired = new Set(s.indicators_fired);
  const prov = new Set(s.provisional_fired);
  const states = ringStates([...fired].map((key) => ({ key, fired: true, provisional: prov.has(key) })));
  const dir = s.direction === "long" ? "Long" : "Short";
  return (
    <li className="border-b border-rule-soft">
      <Link
        href={`/signals/${s.id}`}
        aria-label={`${dir} ${s.instrument}, entry ${p.entry}, ${STRATEGY_NAMES[s.strategy]}, ${STATE_NAMES[s.state]}`}
        className="block px-5 py-3.5 text-ink no-underline hover:bg-selected"
      >
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-2.5">
              <DirectionMarker direction={s.direction} />
              <span className="text-[17px] font-semibold">{s.instrument}</span>
            </div>
            <p className="m-0 mt-0.5 text-[13px] text-mute">
              {STRATEGY_NAMES[s.strategy]} · {STATE_NAMES[s.state]} · <time dateTime={s.created_at}>{age(new Date(s.created_at), now)}</time>
            </p>
            {(s.has_provisional || s.confluence) && (
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {s.has_provisional && <ProvisionalBadge />}
                {s.confluence && (
                  <Badge kind="confluence">
                    <span aria-hidden="true">◆ </span>Both systems agree
                  </Badge>
                )}
              </div>
            )}
          </div>
          {s.strategy === "three_eight" ? (
            <IndicatorRing states={states} direction={s.direction} size={40} />
          ) : (
            <LadderMark direction={s.direction} step={s.direction === "long" ? 1 : -1} />
          )}
        </div>
        <dl className="m-0 mt-3 grid grid-cols-4 gap-2 text-right">
          <PriceCell label="Entry" value={p.entry} strong />
          <PriceCell label="Stop" value={p.stop} />
          <PriceCell label="Target" value={p.target} />
          <PriceCell label="R:R" value={ratio(p.reward_risk)} />
        </dl>
      </Link>
    </li>
  );
}

export function PriceCell({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-mute">{label}</dt>
      <dd className={`m-0 text-[15px] text-ink ${strong ? "font-medium" : ""}`}>{value}</dd>
    </div>
  );
}

export function SignalRowSkeleton() {
  return (
    <li className="border-b border-rule-soft px-5 py-3.5" aria-hidden="true">
      <div className="h-4 w-40 rounded-badge bg-rule-faint motion-safe:animate-pulse" />
      <div className="mt-2 h-3 w-28 rounded-badge bg-rule-faint motion-safe:animate-pulse" />
      <div className="mt-4 h-8 rounded-badge bg-rule-faint motion-safe:animate-pulse" />
    </li>
  );
}
