import { describe, expect, it } from "vitest";
import { allowedText, diffParams, paramLabel, showValue, validateOverride, validateParams, type ParamsSchema } from "./rule-params";

const SCHEMA: ParamsSchema = {
  daily_tolerance_pips: { type: "pips", default: 10, min: 1, max: 50 },
  lookback_bars: { type: "bars", default: 2, min: 1, max: 5 },
  window: { type: "enum", default: "primary", options: ["primary", "alternative", "both"] },
  primary_start: { type: "time", default: "00:00" },
  reject_below_min: { type: "boolean", default: false },
  patterns: { type: "list", default: ["CDLDOJI"], options: ["CDLDOJI", "CDLHAMMER", "SHAVED"] },
};

const GOOD = {
  daily_tolerance_pips: "12.5",
  lookback_bars: "3",
  window: "both",
  primary_start: "05:00",
  reject_below_min: "true",
  patterns: ["CDLHAMMER", "CDLDOJI"],
};

describe("validateParams", () => {
  it("parses every type", () => {
    expect(validateParams(SCHEMA, GOOD)).toEqual({
      ok: true,
      params: {
        daily_tolerance_pips: 12.5,
        lookback_bars: 3,
        window: "both",
        primary_start: "05:00",
        reject_below_min: true,
        patterns: ["CDLDOJI", "CDLHAMMER"],
      },
    });
  });

  it("treats a missing boolean as off", () => {
    const r = validateParams(SCHEMA, { ...GOOD, reject_below_min: undefined });
    expect(r.ok && r.params.reject_below_min).toBe(false);
  });

  it("rejects values outside the schema", () => {
    const r = validateParams(SCHEMA, {
      daily_tolerance_pips: "51",
      lookback_bars: "2.5",
      window: "night",
      primary_start: "24:00",
      patterns: ["CDLEVIL"],
    });
    expect(r).toEqual({
      ok: false,
      errors: {
        daily_tolerance_pips: "Use 50 or less.",
        lookback_bars: "Enter a whole number.",
        window: "Choose one of the options.",
        primary_start: "Use 24-hour time, for example 09:30.",
        patterns: "Choose from the listed options.",
      },
    });
  });

  it("needs every parameter and at least one list item", () => {
    const r = validateParams(SCHEMA, { ...GOOD, daily_tolerance_pips: " ", patterns: [] });
    expect(r).toEqual({ ok: false, errors: { daily_tolerance_pips: "Enter a value.", patterns: "Choose at least one." } });
    expect(validateParams(SCHEMA, { ...GOOD, lookback_bars: "1e3" })).toMatchObject({ ok: false });
    expect(validateParams(SCHEMA, { ...GOOD, daily_tolerance_pips: "0" })).toMatchObject({
      ok: false,
      errors: { daily_tolerance_pips: "Use 1 or more." },
    });
  });
});

describe("validateOverride", () => {
  it("keeps only filled parameters", () => {
    expect(validateOverride(SCHEMA, { daily_tolerance_pips: "20", lookback_bars: "" })).toEqual({
      ok: true,
      params: { daily_tolerance_pips: 20 },
    });
  });

  it("rejects unknown and invalid parameters", () => {
    expect(validateOverride(SCHEMA, { nope: "1", lookback_bars: "9" })).toEqual({
      ok: false,
      errors: { nope: "Unknown parameter.", lookback_bars: "Use 5 or less." },
    });
  });
});

describe("display helpers", () => {
  it("labels and ranges", () => {
    expect(paramLabel("daily_tolerance_pips")).toBe("Daily tolerance");
    expect(paramLabel("window")).toBe("Window");
    expect(paramLabel("parallel_tolerance_pct")).toBe("Parallel tolerance");
    expect(allowedText(SCHEMA.lookback_bars!)).toBe("Allowed 1 to 5");
    expect(allowedText(SCHEMA.window!)).toBeNull();
  });

  it("diffs versions", () => {
    expect(diffParams({ a: 1, b: [1, 2], c: true }, { a: 2, b: [1, 2], c: true, d: "x" })).toEqual([
      { name: "a", before: 1, after: 2 },
      { name: "d", before: undefined, after: "x" },
    ]);
    expect(showValue(false)).toBe("off");
    expect(showValue(["A", "B"])).toBe("A, B");
  });
});
