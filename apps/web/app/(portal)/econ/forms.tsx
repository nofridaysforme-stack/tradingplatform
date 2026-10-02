"use client";

import { Button } from "@/components/ui";
import { useFormAction } from "@/lib/use-form-action";
import { createEconEvent, deleteEconEvent, type EconState } from "./actions";

export function AddEventForm() {
  const [state, onSubmit, pending] = useFormAction<EconState>(createEconEvent, {}, { resetOnSuccess: true });
  const e = state.fieldErrors ?? {};
  const err = (name: string) =>
    e[name] && (
      <p id={`econ-${name}-error`} className="m-0 text-[13px] text-error">
        {e[name]}
      </p>
    );
  const cls = (name: string) =>
    `h-12 w-full min-w-0 rounded-control border bg-input px-3.5 text-base text-ink outline-none ${e[name] ? "border-[1.5px] border-error" : "border-rule focus:border-[1.5px] focus:border-ink"}`;
  const aria = (name: string) => ({ "aria-invalid": e[name] ? true : undefined, "aria-describedby": e[name] ? `econ-${name}-error` : undefined });
  return (
    <form onSubmit={onSubmit} noValidate aria-label="Add event" className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-1.5">
          <label htmlFor="econ-at" className="text-sm text-ink-2">
            Time (New York)
          </label>
          <input id="econ-at" name="at" type="datetime-local" className={cls("at")} {...aria("at")} />
          {err("at")}
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <label htmlFor="econ-currency" className="text-sm text-ink-2">
            Currency
          </label>
          <input id="econ-currency" name="currency" maxLength={3} autoCapitalize="characters" placeholder="USD" className={cls("currency")} {...aria("currency")} />
          {err("currency")}
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <label htmlFor="econ-title" className="text-sm text-ink-2">
            Event
          </label>
          <input id="econ-title" name="title" maxLength={200} placeholder="Nonfarm payrolls" className={cls("title")} {...aria("title")} />
          {err("title")}
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <label htmlFor="econ-impact" className="text-sm text-ink-2">
            Impact
          </label>
          <select id="econ-impact" name="impact" defaultValue="high" className={cls("impact")} {...aria("impact")}>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          {err("impact")}
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
          Add event
        </Button>
      </div>
    </form>
  );
}

export function DeleteEvent({ id, title }: { id: string; title: string }) {
  const [state, onSubmit, pending] = useFormAction<EconState>(deleteEconEvent, {});
  return (
    <form onSubmit={onSubmit}>
      <input type="hidden" name="id" value={id} />
      <Button kind="inline" type="submit" disabled={pending} aria-label={`Delete ${title}`}>
        Delete
      </Button>
      {state.error && (
        <span role="alert" className="ml-2 text-[13px] text-error">
          {state.error}
        </span>
      )}
    </form>
  );
}
