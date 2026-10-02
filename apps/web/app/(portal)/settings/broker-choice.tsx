"use client";

import { Button } from "@/components/ui";
import { useFormAction } from "@/lib/use-form-action";
import { setActiveBroker, type ActionState } from "../signals/actions";

/** Each owner picks the broker whose spreads adjust their prices (spec 10). */
export function BrokerChoice({ current, brokers }: { current: string | null; brokers: { id: string; name: string }[] }) {
  const [state, onSubmit, pending] = useFormAction<ActionState>(setActiveBroker, {});
  if (brokers.length === 0) {
    return <p className="m-0 text-sm text-ink-2">No brokers yet. An admin adds them under Brokers.</p>;
  }
  return (
    <form onSubmit={onSubmit} aria-label="Broker for adjusted prices" className="flex flex-col gap-3">
      <fieldset className="m-0 border-0 p-0">
        <legend className="sr-only">Broker for adjusted prices</legend>
        {brokers.map((b) => (
          <label key={b.id} className="flex min-h-11 items-center gap-3 border-b border-rule-faint text-sm">
            <input type="radio" name="brokerId" value={b.id} defaultChecked={b.id === current} className="size-4 accent-[var(--ink)]" />
            {b.name}
          </label>
        ))}
        <label className="flex min-h-11 items-center gap-3 border-b border-rule-faint text-sm">
          <input type="radio" name="brokerId" value="" defaultChecked={!current} className="size-4 accent-[var(--ink)]" />
          No broker (reference prices)
        </label>
      </fieldset>
      {state.error && (
        <p role="alert" className="m-0 text-[13px] text-error">
          {state.error}
        </p>
      )}
      {state.ok && (
        <p role="status" className="m-0 text-sm font-medium text-ink">
          Broker saved
        </p>
      )}
      <div>
        <Button kind="secondary" type="submit" disabled={pending}>
          Save broker
        </Button>
      </div>
    </form>
  );
}
