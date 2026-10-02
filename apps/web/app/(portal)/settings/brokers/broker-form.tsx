"use client";

import { Button } from "@/components/ui";
import { useFormAction } from "@/lib/use-form-action";
import { deleteBroker, saveBroker, type BrokerState } from "./actions";

export interface BrokerValues {
  id?: string;
  name: string;
  template: string;
  notes: string;
  spreads: Record<string, { pips: string; symbol: string }>;
}

const input = (bad: boolean) =>
  `h-11 w-full min-w-0 rounded-control border bg-input px-3 text-base text-ink outline-none ${bad ? "border-[1.5px] border-error" : "border-rule focus:border-[1.5px] focus:border-ink"}`;

export function BrokerForm({ values, pairs, idPrefix }: { values: BrokerValues; pairs: { id: string; symbol: string }[]; idPrefix: string }) {
  const editing = Boolean(values.id);
  const [state, onSubmit, pending] = useFormAction<BrokerState>(saveBroker, {}, { resetOnSuccess: !editing });
  const e = state.fieldErrors ?? {};
  const text = (name: "name" | "template" | "notes", label: string, hint?: string) => {
    const id = `${idPrefix}-${name}`;
    const err = e[name];
    return (
      <div className="flex min-w-0 flex-col gap-1.5">
        <label htmlFor={id} className="text-sm text-ink-2">
          {label}
        </label>
        <input
          id={id}
          name={name}
          defaultValue={values[name]}
          aria-invalid={err ? true : undefined}
          aria-describedby={[hint ? `${id}-hint` : "", err ? `${id}-error` : ""].filter(Boolean).join(" ") || undefined}
          className={input(Boolean(err))}
        />
        {hint && (
          <p id={`${id}-hint`} className="m-0 text-[13px] text-mute">
            {hint}
          </p>
        )}
        {err && (
          <p id={`${id}-error`} className="m-0 text-[13px] text-error">
            {err}
          </p>
        )}
      </div>
    );
  };
  return (
    <form onSubmit={onSubmit} noValidate aria-label={editing ? `Edit ${values.name}` : "Add broker"} className="flex flex-col gap-4">
      {values.id && <input type="hidden" name="id" value={values.id} />}
      {text("name", "Name")}
      {text("template", "Chart link (optional)", "An https address with {symbol} where the pair goes, for example https://trade.example.com/chart?symbol={symbol}")}
      {text("notes", "Notes (optional)")}
      <fieldset className="m-0 border-0 p-0">
        <legend className="mb-1 text-sm text-ink-2">Typical spread per pair</legend>
        <p className="m-0 mb-2 text-[13px] text-mute">Leave a spread blank to show reference prices for that pair.</p>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-xs text-mute">
              <th scope="col" className="pb-1.5 text-left font-normal">
                Pair
              </th>
              <th scope="col" className="pb-1.5 pl-2 text-left font-normal">
                Spread (pips)
              </th>
              <th scope="col" className="pb-1.5 pl-2 text-left font-normal">
                Broker symbol (optional)
              </th>
            </tr>
          </thead>
          <tbody>
            {pairs.map((p) => {
              const sErr = e[`spread.${p.id}`];
              const yErr = e[`symbol.${p.id}`];
              return (
                <tr key={p.id} className="border-t border-rule-soft align-top">
                  <th scope="row" className="py-2 text-left font-normal">
                    {p.symbol}
                  </th>
                  <td className="py-2 pl-2">
                    <input
                      name={`spread.${p.id}`}
                      inputMode="decimal"
                      aria-label={`${p.symbol} spread in pips`}
                      defaultValue={values.spreads[p.id]?.pips ?? ""}
                      aria-invalid={sErr ? true : undefined}
                      className={input(Boolean(sErr))}
                    />
                    {sErr && <span className="mt-1 block text-[13px] text-error">{sErr}</span>}
                  </td>
                  <td className="py-2 pl-2">
                    <input
                      name={`symbol.${p.id}`}
                      aria-label={`${p.symbol} symbol at this broker`}
                      placeholder={p.symbol.replace("/", "")}
                      defaultValue={values.spreads[p.id]?.symbol ?? ""}
                      aria-invalid={yErr ? true : undefined}
                      className={input(Boolean(yErr))}
                    />
                    {yErr && <span className="mt-1 block text-[13px] text-error">{yErr}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </fieldset>
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
          {editing ? "Save broker" : "Add broker"}
        </Button>
      </div>
    </form>
  );
}

export function DeleteBroker({ id, name }: { id: string; name: string }) {
  const [state, onSubmit, pending] = useFormAction<BrokerState>(deleteBroker, {});
  return (
    <form
      onSubmit={(ev) => {
        if (!window.confirm(`Delete ${name}? Owners using it will see reference prices.`)) {
          ev.preventDefault();
          return;
        }
        onSubmit(ev);
      }}
    >
      <input type="hidden" name="id" value={id} />
      <Button kind="inline" type="submit" disabled={pending} aria-label={`Delete ${name}`}>
        Delete broker
      </Button>
      {state.error && (
        <span role="alert" className="ml-2 text-[13px] text-error">
          {state.error}
        </span>
      )}
    </form>
  );
}
