"use client";

import { Button } from "@/components/ui";
import { useFormAction } from "@/lib/use-form-action";
import { createHolding, updateHolding, type HoldingState } from "@/app/(portal)/holdings/actions";

interface Values {
  id?: string;
  ticker: string;
  purchasePrice: string;
  purchaseDate: string;
  expectedProfitPct: number;
  horizonSessions: number;
  notes?: string | null;
}

/** Add or edit a holding (spec 08: ticker, purchase price, date, expected profit). */
export function HoldingForm({ values, idPrefix, submit, lockTicker = false }: { values: Values; idPrefix: string; submit: string; lockTicker?: boolean }) {
  const editing = Boolean(values.id);
  const [state, onSubmit, pending] = useFormAction<HoldingState>(editing ? updateHolding : createHolding, {}, { resetOnSuccess: !editing });
  const e = state.fieldErrors ?? {};
  const field = (name: keyof Values, label: string, props: React.InputHTMLAttributes<HTMLInputElement>, suffix?: string) => {
    const id = `${idPrefix}-${name}`;
    return (
      <div className="flex min-w-0 flex-col gap-1.5">
        <label htmlFor={id} className="text-sm text-ink-2">
          {label}
        </label>
        <span className="flex items-center gap-2">
          <input
            id={id}
            name={name}
            defaultValue={values[name] === null || values[name] === undefined ? "" : String(values[name])}
            aria-invalid={e[name] ? true : undefined}
            aria-describedby={e[name] ? `${id}-error` : undefined}
            className={`h-12 w-full min-w-0 rounded-control border bg-input px-3.5 text-base text-ink outline-none ${e[name] ? "border-[1.5px] border-error" : "border-rule focus:border-[1.5px] focus:border-ink"}`}
            {...props}
          />
          {suffix && <span className="text-[13px] text-mute">{suffix}</span>}
        </span>
        {e[name] && (
          <p id={`${id}-error`} className="m-0 text-[13px] text-error">
            {e[name]}
          </p>
        )}
      </div>
    );
  };
  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4" aria-label={submit}>
      {values.id && <input type="hidden" name="id" value={values.id} />}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {lockTicker ? (
          <input type="hidden" name="ticker" value={values.ticker} />
        ) : (
          field("ticker", "Ticker", { autoCapitalize: "characters", autoComplete: "off", maxLength: 10 })
        )}
        {field("purchasePrice", "Purchase price", { inputMode: "decimal" })}
        {field("purchaseDate", "Purchase date", { type: "date" })}
        {field("expectedProfitPct", "Expected profit", { inputMode: "decimal" }, "%")}
        {field("horizonSessions", "Horizon", { inputMode: "numeric" }, "sessions")}
        {field("notes", "Notes (optional)", { maxLength: 500 })}
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
          {submit}
        </Button>
      </div>
    </form>
  );
}
