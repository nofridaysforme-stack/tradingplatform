"use client";

import { ParamInput } from "@/components/param-input";
import { Button } from "@/components/ui";
import { paramLabel, showValue, type ParamsSchema } from "@/lib/rule-params";
import { useFormAction } from "@/lib/use-form-action";
import { setRuleOverride, type RuleActionState } from "./actions";

interface Props {
  ruleKey: string;
  schema: ParamsSchema;
  overrides: { instrumentId: string; symbol: string; params: Record<string, unknown> }[];
  pairs: { id: string; symbol: string }[];
}

/** Per-pair overrides (spec 05): an override wins over the rule version's value. */
export function Overrides({ ruleKey, schema, overrides, pairs }: Props) {
  const [state, onSubmit, pending] = useFormAction<RuleActionState>(setRuleOverride, {}, { resetOnSuccess: true });
  const e = state.fieldErrors ?? {};
  const editable = Object.entries(schema);
  if (editable.length === 0) return <p className="m-0 text-sm text-ink-2">This rule has no parameters to override.</p>;
  return (
    <div className="flex flex-col gap-4">
      {overrides.length === 0 ? (
        <p className="m-0 text-sm text-ink-2">No overrides. Every pair uses the rule&apos;s values.</p>
      ) : (
        <ul className="m-0 list-none p-0">
          {overrides.map((o) => (
            <li key={o.instrumentId} className="flex flex-wrap items-center justify-between gap-3 border-b border-rule-soft py-2.5 text-sm">
              <span>
                <strong className="font-semibold">{o.symbol}</strong>{" "}
                <span className="text-ink-2">
                  {Object.entries(o.params)
                    .map(([k, v]) => `${paramLabel(k)} ${showValue(v)}`)
                    .join(" · ")}
                </span>
              </span>
              <form onSubmit={onSubmit}>
                <input type="hidden" name="key" value={ruleKey} />
                <input type="hidden" name="instrumentId" value={o.instrumentId} />
                <input type="hidden" name="intent" value="remove" />
                <Button kind="inline" type="submit" disabled={pending} aria-label={`Remove override for ${o.symbol}`}>
                  Remove override
                </Button>
              </form>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={onSubmit} className="flex flex-col" noValidate aria-label="Set a per-pair override">
        <input type="hidden" name="key" value={ruleKey} />
        <input type="hidden" name="intent" value="save" />
        <div className="flex flex-col gap-2">
          <label htmlFor="override-pair" className="text-sm text-ink-2">
            Pair
          </label>
          <select id="override-pair" name="instrumentId" required className="h-11 rounded-control border border-rule bg-input px-2.5 text-sm text-ink">
            {pairs.map((p) => (
              <option key={p.id} value={p.id}>
                {p.symbol}
              </option>
            ))}
          </select>
        </div>
        <p className="m-0 mt-3 text-[13px] text-mute">Leave a value blank to keep the rule&apos;s value for that pair.</p>
        {editable.map(([name, spec]) => (
          <ParamInput key={name} formId="override" name={name} spec={spec} value={undefined} error={e[name]} optional placeholder="Rule value" />
        ))}
        {state.error && (
          <p role="alert" className="m-0 mt-3 text-[13px] text-error">
            {state.error}
          </p>
        )}
        {state.ok && (
          <p role="status" className="m-0 mt-3 text-sm font-medium text-ink">
            {state.message}
          </p>
        )}
        <div className="mt-3">
          <Button kind="secondary" type="submit" disabled={pending}>
            Save override
          </Button>
        </div>
      </form>
    </div>
  );
}
