"use client";

import { useRef, useState } from "react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { ParamInput } from "@/components/param-input";
import { Button, Toggle } from "@/components/ui";
import { nextBarClose, nyTime } from "@/lib/format";
import type { ParamsSchema } from "@/lib/rule-params";
import { useFormAction } from "@/lib/use-form-action";
import { saveRuleVersion, type RuleActionState } from "./actions";

interface Props {
  ruleKey: string;
  name: string;
  kind: string;
  schema: ParamsSchema;
  version: number;
  status: "approved" | "provisional";
  enabled: boolean;
  countsTowardMinimum: boolean;
  description: string;
  params: Record<string, unknown>;
}

export function RuleEditor(p: Props) {
  const form = useRef<HTMLFormElement>(null);
  const [intent, setIntent] = useState<"save" | "approve">("save");
  const [confirming, setConfirming] = useState<null | "save" | "approve">(null);
  const [state, onSubmit, pending] = useFormAction(async (prev: RuleActionState, data: FormData) => {
    const r = await saveRuleVersion(prev, data);
    setConfirming(null);
    return r;
  }, {} as RuleActionState);
  const e = state.fieldErrors ?? {};
  // Computed when the dialog opens, so server and browser render the same markup.
  const [nextBar, setNextBar] = useState("");
  const ask = (which: "save" | "approve") => {
    setIntent(which);
    setNextBar(nyTime(nextBarClose(new Date())));
    setConfirming(which);
  };

  return (
    // The key resets the fields when a new version arrives.
    <form ref={form} onSubmit={onSubmit} key={`${p.ruleKey}-${p.version}`} className="flex flex-col" noValidate aria-label={`Edit ${p.name}`}>
      <input type="hidden" name="key" value={p.ruleKey} />
      <input type="hidden" name="expectedVersion" value={p.version} />
      <input type="hidden" name="intent" value={intent} />

      <Toggle name="enabled" label="Enabled" hint="Off removes the rule from evaluation." defaultChecked={p.enabled} />
      {p.kind === "indicator" && (
        <Toggle
          name="counts"
          label="Counts toward the minimum"
          hint="When on, a fire adds to the 3/8 indicator count."
          defaultChecked={p.countsTowardMinimum}
        />
      )}

      <div className="flex flex-col gap-2 py-3">
        <label htmlFor="rule-description" className="text-sm text-ink-2">
          Description
        </label>
        <textarea
          id="rule-description"
          name="description"
          rows={3}
          defaultValue={p.description}
          aria-invalid={e.description ? true : undefined}
          aria-describedby={e.description ? "rule-description-error" : undefined}
          className={`rounded-control border bg-input px-3.5 py-2.5 text-base text-ink outline-none ${e.description ? "border-[1.5px] border-error" : "border-rule focus:border-[1.5px] focus:border-ink"}`}
        />
        {e.description && (
          <p id="rule-description-error" className="m-0 text-[13px] text-error">
            {e.description}
          </p>
        )}
      </div>

      {Object.keys(p.schema).length > 0 && (
        <fieldset className="m-0 border-0 p-0">
          <legend className="pt-2 text-sm font-semibold">Parameters</legend>
          {Object.entries(p.schema).map(([name, spec]) => (
            <ParamInput key={name} formId="rule" name={name} spec={spec} value={p.params[name] ?? spec.default} error={e[name]} />
          ))}
        </fieldset>
      )}

      <div className="flex flex-col gap-2 py-4">
        <label htmlFor="rule-note" className="text-sm text-ink-2">
          Change note
        </label>
        <input
          id="rule-note"
          name="note"
          maxLength={500}
          placeholder="What changed and why"
          aria-invalid={e.note ? true : undefined}
          aria-describedby={e.note ? "rule-note-error" : undefined}
          className={`h-12 rounded-control border bg-input px-3.5 text-base text-ink outline-none ${e.note ? "border-[1.5px] border-error" : "border-rule focus:border-[1.5px] focus:border-ink"}`}
        />
        {e.note && (
          <p id="rule-note-error" className="m-0 text-[13px] text-error">
            {e.note}
          </p>
        )}
      </div>

      {state.error && (
        <p role="alert" className="m-0 mb-3 text-[13px] text-error">
          {state.error}
        </p>
      )}
      {state.ok && (
        <p role="status" className="m-0 mb-3 text-sm font-medium text-ink">
          {state.message}
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        <Button type="button" kind="secondary" onClick={() => ask("save")} disabled={pending}>
          Save new version
        </Button>
        {p.status === "provisional" && (
          <Button type="button" onClick={() => ask("approve")} disabled={pending} className="h-11 text-sm">
            Approve rule
          </Button>
        )}
      </div>

      <ConfirmDialog
        open={confirming !== null}
        title={confirming === "approve" ? `Approve ${p.name} v${p.version + 1}?` : `Save ${p.name} v${p.version + 1}?`}
        confirm={confirming === "approve" ? "Approve rule" : "Save new version"}
        pending={pending}
        onCancel={() => setConfirming(null)}
        onConfirm={() => form.current?.requestSubmit()}
      >
        {confirming === "approve" && <p className="m-0">The provisional badge comes off this rule. </p>}
        <p className="m-0">The scanner will use the change from the next bar, {nextBar} NY.</p>
      </ConfirmDialog>
    </form>
  );
}
