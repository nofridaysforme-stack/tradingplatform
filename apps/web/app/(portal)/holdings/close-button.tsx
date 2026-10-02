"use client";

import { Button } from "@/components/ui";
import { useFormAction } from "@/lib/use-form-action";
import { closeHolding, type HoldingState } from "./actions";

export function CloseHolding({ id, ticker }: { id: string; ticker: string }) {
  const [state, onSubmit, pending] = useFormAction<HoldingState>(closeHolding, {});
  return (
    <form onSubmit={onSubmit} className="flex items-center gap-3">
      <input type="hidden" name="id" value={id} />
      <Button kind="inline" type="submit" disabled={pending} aria-label={`Close holding ${ticker}`}>
        Close holding
      </Button>
      {state.error && (
        <span role="alert" className="text-[13px] text-error">
          {state.error}
        </span>
      )}
    </form>
  );
}
