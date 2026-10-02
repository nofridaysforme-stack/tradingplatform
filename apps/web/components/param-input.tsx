import { allowedText, isNumeric, paramLabel, UNITS, type ParamSpec } from "@/lib/rule-params";

/** One parameter editor row (handoff): name | value with unit | "Allowed 2 to 5". */
export function ParamInput({
  formId,
  name,
  spec,
  value,
  error,
  placeholder,
  optional = false,
}: {
  formId: string;
  name: string;
  spec: ParamSpec;
  value: unknown;
  error?: string;
  placeholder?: string;
  optional?: boolean;
}) {
  const id = `${formId}-${name}`;
  const field = `p.${name}`;
  const help = allowedText(spec);
  const describedBy = [help ? `${id}-help` : "", error ? `${id}-error` : ""].filter(Boolean).join(" ") || undefined;
  const border = error ? "border-[1.5px] border-error" : "border-rule focus:border-[1.5px] focus:border-ink";
  const label = (
    <span className="text-sm text-ink">
      {paramLabel(name)}
      <span className="sr-only"> ({name})</span>
    </span>
  );

  let control;
  if (spec.type === "boolean" && !optional) {
    control = (
      <input id={id} type="checkbox" name={field} value="true" defaultChecked={value === true} className="size-5 accent-[var(--ink)]" aria-describedby={describedBy} />
    );
  } else if (spec.type === "enum" || (spec.type === "boolean" && optional)) {
    const options = spec.type === "boolean" ? ["true", "false"] : (spec.options ?? []).map(String);
    control = (
      <select id={id} name={field} defaultValue={value === undefined ? "" : String(value)} aria-describedby={describedBy} className={`h-11 rounded-control border bg-input px-2.5 text-sm text-ink ${border}`}>
        {optional && <option value="">{placeholder ?? "Use the rule value"}</option>}
        {options.map((o) => (
          <option key={o} value={o}>
            {spec.type === "boolean" ? (o === "true" ? "On" : "Off") : o.replaceAll("_", " ")}
          </option>
        ))}
      </select>
    );
  } else if (spec.type === "list") {
    const chosen = Array.isArray(value) ? value.map(String) : [];
    return (
      <fieldset className="m-0 border-0 border-b border-rule-soft p-0 py-3" aria-describedby={describedBy}>
        <legend className="mb-1.5 text-sm text-ink">{paramLabel(name)}</legend>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {(spec.options ?? []).map((o) => (
            <label key={String(o)} className="flex min-h-11 items-center gap-2 text-[13px] text-ink-2">
              <input type="checkbox" name={field} value={String(o)} defaultChecked={chosen.includes(String(o))} className="size-4 accent-[var(--ink)]" />
              {String(o)}
            </label>
          ))}
        </div>
        {!optional && <input type="hidden" name="lists" value={name} />}
        {error && (
          <p id={`${id}-error`} className="m-0 mt-1 text-[13px] text-error">
            {error}
          </p>
        )}
      </fieldset>
    );
  } else {
    const unit = UNITS[spec.type];
    control = (
      <span className="flex items-center gap-2">
        <input
          id={id}
          name={field}
          type={spec.type === "time" ? "time" : "text"}
          inputMode={isNumeric(spec) ? "decimal" : undefined}
          defaultValue={value === undefined ? "" : String(value)}
          placeholder={placeholder}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={`h-11 w-28 rounded-control border bg-input px-3 text-base text-ink outline-none ${border}`}
        />
        {unit && <span className="text-[13px] text-mute">{unit}</span>}
      </span>
    );
  }
  return (
    <div className="grid grid-cols-1 gap-x-4 gap-y-1.5 border-b border-rule-soft py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <label htmlFor={id}>{label}</label>
      <div className="flex flex-col gap-1 sm:items-end">
        {control}
        {help && (
          <span id={`${id}-help`} className="text-xs text-mute">
            {help}
          </span>
        )}
        {error && (
          <span id={`${id}-error`} className="text-[13px] text-error">
            {error}
          </span>
        )}
      </div>
    </div>
  );
}
