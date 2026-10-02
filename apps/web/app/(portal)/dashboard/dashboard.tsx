"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useActionState, useEffect, useState } from "react";
import { HealthDot } from "@/components/health-dot";
import { IndicatorRing } from "@/components/ring";
import { SignalRow } from "@/components/signal-row";
import { Button } from "@/components/ui";
import type { MarketView } from "@/lib/market";
import { staleBanner } from "@/lib/market";
import { pips } from "@/lib/format";
import type { DailyGoal, SignalListItem, StockDigest } from "@/lib/signals";
import { setActiveBroker, type ActionState } from "../signals/actions";

interface Props {
  serverNow: string;
  signals: SignalListItem[];
  market: MarketView;
  broker: { id: string; name: string } | null;
  brokers: { id: string; name: string }[];
  goal: DailyGoal | null;
  digest: StockDigest | null;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url} answered ${res.status}`);
  return (await res.json()) as T;
}

const EMPTY = Array(8).fill("off") as "off"[];

export function Dashboard(props: Props) {
  const signals = useQuery({
    queryKey: ["signals", "live"],
    queryFn: () => getJson<{ signals: SignalListItem[] }>("/api/signals?state=open,confirmed").then((r) => r.signals),
    initialData: props.signals,
  });
  const market = useQuery({
    queryKey: ["market-status"],
    queryFn: () => getJson<MarketView>("/api/market-status"),
    initialData: props.market,
  });
  // Ages ("12 min ago") follow the clock between polls.
  const [now, setNow] = useState(() => new Date(props.serverNow));
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);

  const m = market.data;
  return (
    <main>
      <header className="px-5 pt-6 pb-3.5">
        <div className="flex items-center justify-between gap-3">
          <h1 className="m-0 text-[22px] font-semibold leading-tight">Signals</h1>
          <HealthDot health={m.health} />
        </div>
        <p className="m-0 mt-1 text-[13px] text-ink-2" aria-live="polite">
          {m.line}
        </p>
        <BrokerLine broker={props.broker} brokers={props.brokers} />
      </header>

      {m.stale.map((symbol) => (
        <p key={symbol} role="status" className="m-0 border-b border-warn-border bg-warn-bg px-5 py-3 text-[13px] text-warn-ink">
          {staleBanner(symbol)}
        </p>
      ))}
      {signals.isError && (
        <p role="alert" className="m-0 border-t border-rule px-5 py-3 text-[13px] text-ink-2">
          Signals couldn&apos;t refresh. Check your connection; the list updates again on its own.
        </p>
      )}

      {signals.data.length === 0 ? (
        <section className="flex flex-col items-center gap-4 border-t border-rule px-5 py-14 text-center">
          <IndicatorRing states={EMPTY} direction="long" size={72} showCount={false} label="No signals" />
          <p className="m-0 max-w-[280px] text-sm text-ink-2">
            No open signals. The scanner checks every 15 minutes while the market is open.
          </p>
        </section>
      ) : (
        <section aria-label="Live signals" className="border-t border-rule">
          <ul className="m-0 list-none p-0">
            {signals.data.map((s) => (
              <SignalRow key={s.id} s={s} now={now} />
            ))}
          </ul>
        </section>
      )}

      {props.goal && <Goal goal={props.goal} />}
      {props.digest && <Digest digest={props.digest} />}
    </main>
  );
}

function BrokerLine({ broker, brokers }: { broker: Props["broker"]; brokers: Props["brokers"] }) {
  const [open, setOpen] = useState(false);
  const client = useQueryClient();
  const [state, action, pending] = useActionState(async (prev: ActionState, form: FormData) => {
    const result = await setActiveBroker(prev, form);
    if (result.ok) {
      setOpen(false);
      await client.invalidateQueries({ queryKey: ["signals"] });
    }
    return result;
  }, {});
  return (
    <div className="mt-2.5">
      <div className="flex items-center gap-3 text-[13px] text-mute">
        <span>
          {broker ? (
            <>
              Broker <strong className="font-semibold text-ink">{broker.name}</strong>
            </>
          ) : (
            "No broker selected"
          )}
        </span>
        {brokers.length > 0 && (
          <Button kind="inline" type="button" aria-expanded={open} aria-controls="broker-form" onClick={() => setOpen(!open)}>
            {broker ? "Switch" : "Choose"}
          </Button>
        )}
      </div>
      {!broker && (
        <p className="m-0 mt-1 text-[13px] text-mute">Reference prices. Choose a broker in Settings to see adjusted prices.</p>
      )}
      {open && (
        <form id="broker-form" action={action} className="mt-3 flex flex-col gap-3 border-t border-rule pt-3">
          <fieldset className="m-0 border-0 p-0">
            <legend className="mb-1 text-sm text-ink-2">Broker for adjusted prices</legend>
            {brokers.map((b) => (
              <label key={b.id} className="flex min-h-11 items-center gap-3 border-b border-rule-faint text-sm">
                <input type="radio" name="brokerId" value={b.id} defaultChecked={b.id === broker?.id} className="size-4 accent-[var(--ink)]" />
                {b.name}
              </label>
            ))}
            <label className="flex min-h-11 items-center gap-3 text-sm">
              <input type="radio" name="brokerId" value="" defaultChecked={!broker} className="size-4 accent-[var(--ink)]" />
              No broker (reference prices)
            </label>
          </fieldset>
          {state.error && (
            <p role="alert" className="m-0 text-[13px] text-error">
              {state.error}
            </p>
          )}
          <div>
            <Button kind="secondary" type="submit" disabled={pending}>
              Save broker
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

function Goal({ goal }: { goal: DailyGoal }) {
  const pct = (v: number) => `${Math.max(0, Math.min(100, (v / goal.max) * 100))}%`;
  return (
    <section aria-labelledby="goal-h" className="border-t border-rule px-5 py-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="goal-h" className="m-0 text-sm font-medium">
          Today&apos;s goal
        </h2>
        <p className="m-0 text-sm text-ink-2">
          <strong className="text-[17px] font-semibold text-ink">{pips(goal.pips).replace("+", "")}</strong> of {goal.min}–{goal.max} pips
        </p>
      </div>
      <div
        className="relative mt-2.5 h-2 bg-rule-faint"
        role="meter"
        aria-label="Pips today"
        aria-valuemin={0}
        aria-valuemax={goal.max}
        aria-valuenow={Math.max(0, goal.pips)}
      >
        <div className="absolute inset-y-0 left-0 bg-ink" style={{ width: pct(goal.pips) }} />
        <div
          aria-hidden="true"
          className="absolute -inset-y-[3px] border-x border-ink"
          style={{ left: pct(goal.min), width: `calc(${pct(goal.max)} - ${pct(goal.min)})` }}
        />
      </div>
      <p className="m-0 mt-2 text-[13px] text-mute">
        From {goal.signals} closed 3/8 signal{goal.signals === 1 ? "" : "s"}
      </p>
    </section>
  );
}

const WEEKDAY = new Intl.DateTimeFormat("en-US", { weekday: "long", timeZone: "UTC" });

function Digest({ digest }: { digest: StockDigest }) {
  const day = WEEKDAY.format(new Date(`${digest.session}T12:00:00Z`));
  return (
    <section className="flex items-baseline justify-between gap-3 border-t border-rule px-5 py-4 text-sm text-ink-2">
      <p className="m-0">
        <strong className="text-[17px] font-semibold text-ink">{digest.count}</strong> stock{digest.count === 1 ? "" : "s"} newly
        confirmed after {day}&apos;s session
      </p>
      <Link href="/stocks" className="inline-flex min-h-11 items-center text-link">
        Stocks
      </Link>
    </section>
  );
}
