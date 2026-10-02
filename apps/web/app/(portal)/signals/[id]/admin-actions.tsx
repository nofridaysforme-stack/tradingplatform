"use client";

import { useActionState } from "react";
import { Button } from "@/components/ui";
import { addSignalNote, invalidateSignal, type ActionState } from "../actions";

function TextForm({
  signalId,
  name,
  label,
  button,
  done,
  action,
}: {
  signalId: string;
  name: string;
  label: string;
  button: string;
  done: string;
  action: (prev: ActionState, form: FormData) => Promise<ActionState>;
}) {
  const [state, run, pending] = useActionState(action, {});
  const id = `${name}-input`;
  return (
    <form action={run} className="flex flex-col gap-2" noValidate>
      <input type="hidden" name="signalId" value={signalId} />
      <label htmlFor={id} className="text-sm text-ink-2">
        {label}
      </label>
      <textarea
        id={id}
        name={name}
        rows={2}
        maxLength={500}
        aria-invalid={state.error ? true : undefined}
        aria-describedby={state.error ? `${id}-error` : undefined}
        className={`rounded-control border bg-input px-3.5 py-2.5 text-base text-ink outline-none ${state.error ? "border-[1.5px] border-error" : "border-rule focus:border-[1.5px] focus:border-ink"}`}
      />
      {state.error && (
        <p id={`${id}-error`} className="m-0 text-[13px] text-error">
          {state.error}
        </p>
      )}
      {state.ok && (
        <p role="status" className="m-0 text-[13px] text-ink-2">
          {done}
        </p>
      )}
      <div>
        <Button kind="secondary" type="submit" disabled={pending}>
          {button}
        </Button>
      </div>
    </form>
  );
}

export function AdminActions({ signalId, canInvalidate }: { signalId: string; canInvalidate: boolean }) {
  return (
    <section aria-labelledby="admin-h" className="flex flex-col gap-5 border-t border-rule px-5 py-5">
      <h2 id="admin-h" className="m-0 text-base font-semibold">
        Admin
      </h2>
      {canInvalidate && (
        <TextForm
          signalId={signalId}
          name="reason"
          label="Reason for marking invalid"
          button="Mark invalid"
          done="Signal marked invalid"
          action={invalidateSignal}
        />
      )}
      <TextForm signalId={signalId} name="note" label="Note" button="Add note" done="Note added" action={addSignalNote} />
    </section>
  );
}
