"use client";

import { useActionState } from "react";
import { Button, Field, Rule } from "@/components/ui";
import { requestSignInLink, type SignInState } from "./actions";

export function SignInForm({ initial }: { initial: SignInState }) {
  const [state, action, pending] = useActionState(requestSignInLink, initial);
  return (
    <form action={action} className="flex flex-col gap-5" noValidate>
      <Field
        id="email"
        name="email"
        type="email"
        label="Email"
        autoComplete="email"
        inputMode="email"
        required
        defaultValue={state.email}
        error={state.error}
      />
      <Button type="submit" disabled={pending}>
        Email me a sign-in link
      </Button>
      {state.sent && (
        <>
          <Rule />
          <p role="status" className="m-0 text-sm text-ink">
            Check your email for a sign-in link.
          </p>
        </>
      )}
    </form>
  );
}
