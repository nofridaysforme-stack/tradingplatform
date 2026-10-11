"use client";

import { Button } from "@/components/ui";
import { useFormAction } from "@/lib/use-form-action";
import { useState } from "react";
import { addAllowlistEmail, createSignInLink, removeAllowlistEmail, setUserActive, setUserRole, type UserState } from "./actions";

function Feedback({ state }: { state: UserState }) {
  if (state.error && !state.fieldErrors)
    return (
      <span role="alert" className="text-[13px] text-error">
        {state.error}
      </span>
    );
  if (state.ok)
    return (
      <span role="status" className="text-[13px] text-ink">
        {state.message}
      </span>
    );
  return null;
}

export function AddEmailForm() {
  const [state, onSubmit, pending] = useFormAction<UserState>(addAllowlistEmail, {}, { resetOnSuccess: true });
  const err = state.fieldErrors?.email;
  return (
    <form onSubmit={onSubmit} noValidate aria-label="Approve an email" className="flex flex-col gap-3">
      <div className="flex min-w-0 flex-col gap-2">
        <label htmlFor="allow-email" className="text-sm text-ink-2">
          Email
        </label>
        <input
          id="allow-email"
          name="email"
          type="email"
          autoComplete="off"
          aria-invalid={err ? true : undefined}
          aria-describedby={err ? "allow-email-error" : undefined}
          className={`h-12 w-full min-w-0 rounded-control border bg-input px-3.5 text-base text-ink outline-none ${err ? "border-[1.5px] border-error" : "border-rule focus:border-[1.5px] focus:border-ink"}`}
        />
        {err && (
          <p id="allow-email-error" className="m-0 text-[13px] text-error">
            {err}
          </p>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button kind="secondary" type="submit" disabled={pending}>
          Approve email
        </Button>
        <Feedback state={state} />
      </div>
    </form>
  );
}

export function UserControls({ id, email, role, active, self }: { id: string; email: string; role: "owner" | "admin"; active: boolean; self: boolean }) {
  const [roleState, onRole, rolePending] = useFormAction<UserState>(setUserRole, {});
  const [activeState, onActive, activePending] = useFormAction<UserState>(setUserActive, {});
  return (
    <div className="flex flex-wrap items-center gap-3">
      <form onSubmit={onRole} className="flex flex-wrap items-center gap-2">
        <input type="hidden" name="id" value={id} />
        <label htmlFor={`role-${id}`} className="sr-only">
          Role for {email}
        </label>
        <select id={`role-${id}`} name="role" defaultValue={role} className="h-8 rounded-control border border-rule bg-input px-2 text-[13px] text-ink">
          <option value="owner">Owner</option>
          <option value="admin">Admin</option>
        </select>
        <Button kind="inline" type="submit" disabled={rolePending} aria-label={`Save role for ${email}`}>
          Save role
        </Button>
      </form>
      {!self && (
        <form onSubmit={onActive}>
          <input type="hidden" name="id" value={id} />
          <input type="hidden" name="active" value={active ? "false" : "true"} />
          <Button kind="inline" type="submit" disabled={activePending} aria-label={`${active ? "Deactivate" : "Reactivate"} ${email}`}>
            {active ? "Deactivate" : "Reactivate"}
          </Button>
        </form>
      )}
      <Feedback state={roleState} />
      <Feedback state={activeState} />
    </div>
  );
}

export function RemoveEmail({ email }: { email: string }) {
  const [state, onSubmit, pending] = useFormAction<UserState>(removeAllowlistEmail, {});
  return (
    <form onSubmit={onSubmit} className="flex flex-wrap items-center gap-3">
      <input type="hidden" name="email" value={email} />
      <Button kind="inline" type="submit" disabled={pending} aria-label={`Remove ${email}`}>
        Remove
      </Button>
      <Feedback state={state} />
    </form>
  );
}

/** Makes a sign-in link the admin sends to the person themselves (text or chat). */
export function SignInLink({ email }: { email: string }) {
  const [state, onSubmit, pending] = useFormAction<UserState>(createSignInLink, {});
  const [copied, setCopied] = useState(false);
  const id = `link-${email.replace(/[^a-z0-9]/gi, "-")}`;
  return (
    <div className="mt-2 flex flex-col gap-2">
      <form onSubmit={onSubmit} className="flex flex-wrap items-center gap-3">
        <input type="hidden" name="email" value={email} />
        <Button kind="inline" type="submit" disabled={pending} aria-label={`Create a sign-in link for ${email}`}>
          Create sign-in link
        </Button>
        {state.error && (
          <span role="alert" className="text-[13px] text-error">
            {state.error}
          </span>
        )}
      </form>
      {state.ok && state.link && (
        <div className="flex flex-col gap-1.5">
          <label htmlFor={id} className="text-[13px] text-ink-2">
            Sign-in link for {email}. Send it only to them. It works once, within 24 hours.
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <input
              id={id}
              readOnly
              value={state.link}
              onFocus={(e) => e.currentTarget.select()}
              className="h-10 min-w-0 flex-1 rounded-control border border-rule bg-input px-2.5 text-[13px] text-ink"
            />
            <Button
              kind="secondary"
              type="button"
              onClick={async () => {
                await navigator.clipboard.writeText(state.link!).catch(() => {});
                setCopied(true);
              }}
            >
              Copy link
            </Button>
            {copied && (
              <span role="status" className="text-[13px] text-ink">
                Copied
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
