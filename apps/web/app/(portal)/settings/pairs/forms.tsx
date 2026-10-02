"use client";

import { useState } from "react";
import { Button, Toggle } from "@/components/ui";
import { defaultPipSize, normalizePair, PIP_SIZES, type PipSize } from "@/lib/pairs";
import { useFormAction } from "@/lib/use-form-action";
import { addPair, updatePair, type PairState } from "./actions";

export function PairRow({ id, symbol, enabled, sortOrder }: { id: string; symbol: string; enabled: boolean; sortOrder: number }) {
  const [state, onSubmit, pending] = useFormAction<PairState>(updatePair, {});
  return (
    <form onSubmit={onSubmit} aria-label={`${symbol} settings`} className="flex flex-wrap items-end gap-4">
      <input type="hidden" name="id" value={id} />
      <div className="min-w-[200px] flex-1">
        <Toggle name="enabled" label={`Scan ${symbol}`} defaultChecked={enabled} />
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor={`order-${id}`} className="text-xs text-mute">
          Order
        </label>
        <input
          id={`order-${id}`}
          name="sortOrder"
          inputMode="numeric"
          defaultValue={sortOrder}
          className="h-11 w-20 rounded-control border border-rule bg-input px-3 text-base text-ink"
        />
      </div>
      <Button kind="inline" type="submit" disabled={pending} aria-label={`Save ${symbol}`}>
        Save
      </Button>
      {state.error && (
        <span role="alert" className="text-[13px] text-error">
          {state.error}
        </span>
      )}
      {state.ok && (
        <span role="status" className="text-[13px] text-ink">
          {state.message}
        </span>
      )}
    </form>
  );
}

export function AddPairForm() {
  const [state, onSubmit, pending] = useFormAction<PairState>(addPair, {}, { resetOnSuccess: true });
  const [pip, setPip] = useState<PipSize>("0.0001");
  const e = state.fieldErrors ?? {};
  return (
    <form onSubmit={onSubmit} noValidate aria-label="Add pair" className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-1.5">
          <label htmlFor="pair-symbol" className="text-sm text-ink-2">
            Pair
          </label>
          <input
            id="pair-symbol"
            name="symbol"
            placeholder="EUR/GBP"
            autoCapitalize="characters"
            autoComplete="off"
            onChange={(ev) => {
              const s = normalizePair(ev.currentTarget.value);
              if (s) setPip(defaultPipSize(s));
            }}
            aria-invalid={e.symbol ? true : undefined}
            aria-describedby={e.symbol ? "pair-symbol-error" : undefined}
            className={`h-12 w-full min-w-0 rounded-control border bg-input px-3.5 text-base text-ink outline-none ${e.symbol ? "border-[1.5px] border-error" : "border-rule focus:border-[1.5px] focus:border-ink"}`}
          />
          {e.symbol && (
            <p id="pair-symbol-error" className="m-0 text-[13px] text-error">
              {e.symbol}
            </p>
          )}
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <label htmlFor="pair-pip" className="text-sm text-ink-2">
            Pip size
          </label>
          <select
            id="pair-pip"
            name="pipSize"
            value={pip}
            onChange={(ev) => setPip(ev.currentTarget.value as PipSize)}
            aria-describedby="pair-pip-help"
            className="h-12 w-full min-w-0 rounded-control border border-rule bg-input px-3 text-base text-ink"
          >
            {PIP_SIZES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <p id="pair-pip-help" className="m-0 text-[13px] text-mute">
            0.01 for yen pairs, 0.0001 for the rest. It can&apos;t be changed after the pair is added.
          </p>
        </div>
      </div>
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
        <Button kind="secondary" type="submit" disabled={pending}>
          Add pair
        </Button>
      </div>
    </form>
  );
}
