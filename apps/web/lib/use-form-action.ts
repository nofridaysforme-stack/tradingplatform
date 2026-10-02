"use client";

import { startTransition, useActionState, useEffect, useRef, type FormEvent } from "react";

/**
 * Like useActionState with a form `action`, but React does not reset the form after the
 * submit, so a validation error keeps what the person typed. With resetOnSuccess the form
 * clears once the action returns { ok: true }.
 */
export function useFormAction<S extends { ok?: boolean }>(
  action: (prev: S, form: FormData) => Promise<S>,
  initial: S,
  { resetOnSuccess = false }: { resetOnSuccess?: boolean } = {},
) {
  // S is a plain state object, never a promise, so Awaited<S> is S.
  const [state, dispatch, pending] = useActionState<S, FormData>(action, initial as Awaited<S>);
  const last = useRef<HTMLFormElement | null>(null);
  useEffect(() => {
    if (resetOnSuccess && state.ok) last.current?.reset();
  }, [state, resetOnSuccess]);
  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    last.current = e.currentTarget;
    const data = new FormData(e.currentTarget, (e.nativeEvent as SubmitEvent).submitter);
    startTransition(() => dispatch(data));
  };
  return [state, onSubmit, pending] as const;
}
