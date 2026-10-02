import { describe, expect, it } from "vitest";
import { cumulative, summarize } from "./metrics";

const t = (state: string, resultPips: number) => ({ state, resultPips });

describe("summarize", () => {
  it("is empty without trades", () => {
    expect(summarize([])).toEqual({ trades: 0, wins: 0, winRate: 0, netPips: 0, expectancy: 0, profitFactor: null });
  });

  it("follows the backtest definitions", () => {
    const s = summarize([t("target_hit", 40), t("stop_hit", -20), t("expired", 5), t("expired", -5), t("target_hit", 30)]);
    expect(s).toEqual({ trades: 5, wins: 2, winRate: 0.4, netPips: 50, expectancy: 10, profitFactor: 3 });
  });

  it("leaves invalidated signals out", () => {
    expect(summarize([t("target_hit", 40), t("invalidated", -100)]).trades).toBe(1);
  });

  it("has no profit factor without losses, and counts a zero result as a loss", () => {
    expect(summarize([t("target_hit", 10)]).profitFactor).toBeNull();
    expect(summarize([t("target_hit", 10), t("expired", 0)]).profitFactor).toBeNull();
    expect(summarize([t("target_hit", 10), t("expired", 0)]).expectancy).toBe(5);
  });
});

describe("cumulative", () => {
  it("adds results in order and skips invalidated signals", () => {
    const rows = [
      { state: "target_hit", resultPips: 41, closedAt: "a" },
      { state: "invalidated", resultPips: 99, closedAt: "b" },
      { state: "stop_hit", resultPips: -23, closedAt: "c" },
    ];
    expect(cumulative(rows)).toEqual([
      { at: "a", pips: 41 },
      { at: "c", pips: 18 },
    ]);
  });
});
