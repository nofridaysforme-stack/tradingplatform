"use client";

import { useState } from "react";
import { Button, Toggle } from "@/components/ui";
import { useFormAction } from "@/lib/use-form-action";
import { setStrategyConfig, type RuleActionState } from "./actions";

interface Props {
  strategy: "three_eight" | "fib_pivot" | "stocks";
  name: string;
  enabled: boolean;
  instrumentIds: string[] | null;
  pairs: { id: string; symbol: string; enabled: boolean }[];
}

/** The strategy's master switch and, for forex, the pairs it scans. */
export function StrategySwitch({ strategy, name, enabled, instrumentIds, pairs }: Props) {
  const [state, onSubmit, pending] = useFormAction<RuleActionState>(setStrategyConfig, {});
  const [some, setSome] = useState(instrumentIds !== null);
  const forex = strategy !== "stocks";
  return (
    <form onSubmit={onSubmit} aria-label={`${name} settings`} className="flex flex-col gap-2 pb-3">
      <input type="hidden" name="strategy" value={strategy} />
      <Toggle name="enabled" label={`Scan with the ${name}`} defaultChecked={enabled} />
      {forex && (
        <fieldset className="m-0 border-0 p-0">
          <legend className="text-[13px] text-mute">Pairs</legend>
          <label className="flex min-h-11 items-center gap-2 text-sm">
            <input type="radio" name="pairs" value="all" defaultChecked={!some} onChange={() => setSome(false)} className="size-4 accent-[var(--ink)]" />
            All enabled pairs
          </label>
          <label className="flex min-h-11 items-center gap-2 text-sm">
            <input type="radio" name="pairs" value="some" defaultChecked={some} onChange={() => setSome(true)} className="size-4 accent-[var(--ink)]" />
            Only these pairs
          </label>
          {some && (
            <div className="flex flex-wrap gap-x-4 pl-6">
              {pairs.map((p) => (
                <label key={p.id} className="flex min-h-11 items-center gap-2 text-[13px]">
                  <input
                    type="checkbox"
                    name="instrumentIds"
                    value={p.id}
                    defaultChecked={instrumentIds?.includes(p.id) ?? false}
                    className="size-4 accent-[var(--ink)]"
                  />
                  {p.symbol}
                  {!p.enabled && <span className="text-mute">(pair off)</span>}
                </label>
              ))}
            </div>
          )}
        </fieldset>
      )}
      {state.error && (
        <p role="alert" className="m-0 text-[13px] text-error">
          {state.error}
        </p>
      )}
      {state.ok && (
        <p role="status" className="m-0 text-sm font-medium text-ink">
          {state.message}
        </p>
      )}
      <div>
        <Button kind="inline" type="submit" disabled={pending}>
          Save {name} settings
        </Button>
      </div>
    </form>
  );
}
