import { describe, expect, it } from "vitest";
import { ladderRungs } from "./levels-view";

const LADDER = {
  pivot: 1.087,
  fib: 55,
  range: 66,
  up: { break: 1.0925, confirmation: 1.0959, take_profit: 1.1014, reset: 1.1103 },
  down: { break: 1.0815, confirmation: 1.0781, take_profit: 1.0726, reset: 1.0637 },
};

describe("ladderRungs", () => {
  it("lists spec 07 levels from the top reset down to the bottom reset", () => {
    expect(ladderRungs(LADDER, null).map((r) => r.label)).toEqual([
      "Reset up",
      "Take profit up",
      "Confirmation up",
      "Break up",
      "Pivot",
      "Break down",
      "Confirmation down",
      "Take profit down",
      "Reset down",
    ]);
  });

  it("places the current price between the levels around it", () => {
    const labels = ladderRungs(LADDER, 1.09).map((r) => r.label);
    expect(labels.slice(3, 6)).toEqual(["Break up", "Now", "Pivot"]);
    expect(ladderRungs(LADDER, 1.2)[0]?.label).toBe("Now");
    expect(ladderRungs(LADDER, 1.0)?.at(-1)?.label).toBe("Now");
  });
});
