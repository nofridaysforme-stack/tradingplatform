// Rule parameters are checked against the rule's params_schema before any version is saved
// (spec 05, spec 14). The schema is the one seeded with the rule; this only enforces it.

export interface ParamSpec {
  type: string;
  default?: unknown;
  min?: number;
  max?: number;
  options?: (string | number)[];
}
export type ParamsSchema = Record<string, ParamSpec>;
export type ParamValue = number | string | boolean | (string | number)[];

const WHOLE = new Set(["bars", "integer", "sessions", "minutes", "hours"]);
const DECIMAL = new Set(["pips", "percent", "ratio", "price"]);

export const UNITS: Record<string, string> = {
  pips: "pips",
  bars: "bars",
  sessions: "sessions",
  minutes: "minutes",
  hours: "hours",
  percent: "%",
  ratio: "ratio",
  price: "price",
};

export function isNumeric(spec: ParamSpec): boolean {
  return WHOLE.has(spec.type) || DECIMAL.has(spec.type);
}

/** "Allowed 2 to 5" style help for a parameter. */
export function allowedText(spec: ParamSpec): string | null {
  if (isNumeric(spec) && spec.min !== undefined && spec.max !== undefined) return `Allowed ${spec.min} to ${spec.max}`;
  if (isNumeric(spec) && spec.min !== undefined) return `At least ${spec.min}`;
  if (spec.type === "time") return "24-hour time, New York";
  return null;
}

/** Readable name for a parameter key: daily_tolerance_pips -> "Daily tolerance". */
export function paramLabel(name: string): string {
  const words = name.split("_");
  const unit = words.at(-1);
  const trimmed = words.length > 1 && unit && (UNITS[unit] || unit === "pct") ? words.slice(0, -1) : words;
  const text = trimmed.join(" ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export type Raw = Record<string, string | string[] | undefined>;

/** Parse one raw form value against its spec. Returns the value or an error sentence. */
export function parseParam(spec: ParamSpec, raw: string | string[] | undefined): { value: ParamValue } | { error: string } {
  const one = Array.isArray(raw) ? raw[0] : raw;
  if (spec.type === "boolean") return { value: one === "true" || one === "on" };
  if (spec.type === "list") {
    const picked = (Array.isArray(raw) ? raw : raw ? [raw] : []).filter(Boolean);
    const options = spec.options ?? [];
    const values = options.filter((o) => picked.includes(String(o)));
    if (values.length !== picked.length) return { error: "Choose from the listed options." };
    if (values.length === 0) return { error: "Choose at least one." };
    return { value: values };
  }
  const text = (one ?? "").trim();
  if (text === "") return { error: "Enter a value." };
  if (spec.type === "enum") {
    const match = (spec.options ?? []).find((o) => String(o) === text);
    return match === undefined ? { error: "Choose one of the options." } : { value: match };
  }
  if (spec.type === "time") {
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(text)) return { error: "Use 24-hour time, for example 09:30." };
    return { value: text };
  }
  if (isNumeric(spec)) {
    if (!/^-?\d+(\.\d+)?$/.test(text)) return { error: "Enter a number." };
    const n = Number(text);
    if (WHOLE.has(spec.type) && !Number.isInteger(n)) return { error: "Enter a whole number." };
    if (spec.min !== undefined && n < spec.min) return { error: `Use ${spec.min} or more.` };
    if (spec.max !== undefined && n > spec.max) return { error: `Use ${spec.max} or less.` };
    return { value: n };
  }
  return { error: "This parameter type can't be edited here." };
}

export type Validation = { ok: true; params: Record<string, ParamValue> } | { ok: false; errors: Record<string, string> };

/** Every parameter in the schema, each valid (for a new version). */
export function validateParams(schema: ParamsSchema, raw: Raw): Validation {
  const params: Record<string, ParamValue> = {};
  const errors: Record<string, string> = {};
  for (const [name, spec] of Object.entries(schema)) {
    const r = parseParam(spec, raw[name]);
    if ("error" in r) errors[name] = r.error;
    else params[name] = r.value;
  }
  return Object.keys(errors).length ? { ok: false, errors } : { ok: true, params };
}

/** Only the parameters given (for a per-pair override); blank fields are left out. */
export function validateOverride(schema: ParamsSchema, raw: Raw): Validation {
  const params: Record<string, ParamValue> = {};
  const errors: Record<string, string> = {};
  for (const [name, value] of Object.entries(raw)) {
    const spec = schema[name];
    if (!spec) {
      errors[name] = "Unknown parameter.";
      continue;
    }
    const blank = value === undefined || value === "" || (Array.isArray(value) && value.length === 0);
    if (blank) continue;
    const r = parseParam(spec, value);
    if ("error" in r) errors[name] = r.error;
    else params[name] = r.value;
  }
  return Object.keys(errors).length ? { ok: false, errors } : { ok: true, params };
}

export interface Change {
  name: string;
  before: unknown;
  after: unknown;
}

/** Parameter changes between two versions, in schema order. */
export function diffParams(before: Record<string, unknown>, after: Record<string, unknown>): Change[] {
  const names = [...new Set([...Object.keys(before), ...Object.keys(after)])];
  return names
    .filter((n) => JSON.stringify(before[n]) !== JSON.stringify(after[n]))
    .map((n) => ({ name: n, before: before[n], after: after[n] }));
}

export function showValue(v: unknown): string {
  if (v === undefined || v === null) return "none";
  if (typeof v === "boolean") return v ? "on" : "off";
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}
