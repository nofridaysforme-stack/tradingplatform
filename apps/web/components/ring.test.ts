import { describe, expect, it } from "vitest";
import { INDICATORS, ringStates } from "./ring";

const fact = (key: string, fired: boolean, provisional = false) => ({ key, fired, provisional });

describe("ringStates", () => {
  it("returns one state per indicator in ring order", () => {
    expect(ringStates([])).toEqual(Array(INDICATORS.length).fill("off"));
  });

  it("marks fired indicators, with provisional ones dashed", () => {
    const states = ringStates([
      fact("three_eight.candlestick", true),
      fact("three_eight.trendline_channel", true, true),
      fact("three_eight.fibonacci", false),
    ]);
    expect(states[0]).toBe("fired");
    expect(states[4]).toBe("provisional");
    expect(states[7]).toBe("off");
  });

  it("shows a provisional indicator that did not fire as off", () => {
    expect(ringStates([fact("three_eight.flag_pennant_triangle", false, true)])[3]).toBe("off");
  });

  it("ignores keys that are not ring indicators", () => {
    expect(ringStates([fact("three_eight.target", true)])).toEqual(Array(8).fill("off"));
  });
});
