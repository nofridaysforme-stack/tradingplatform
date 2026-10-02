import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { checkHolding, salesTarget } from "./holdings-math";

interface Case {
  purchase_price: string;
  expected_profit_pct: string;
  horizon_sessions: number;
  last_close: string;
  sessions_elapsed: number;
  expected: { target: number; earnings: number; daily: number; weekly: number; progress: number; target_reached: boolean; time_elapsed: boolean };
}

const FIXTURE = path.resolve(__dirname, "../../../services/scanner/tests/fixtures/holding_cases.json");
const { cases } = JSON.parse(readFileSync(FIXTURE, "utf8")) as { cases: Case[] };

describe("sales targets", () => {
  it.each(cases)("matches the scanner for $purchase_price at $last_close", (c) => {
    const p = Number(c.purchase_price);
    const pct = Number(c.expected_profit_pct);
    const st = salesTarget(p, pct, c.horizon_sessions);
    const ck = checkHolding(p, pct, c.horizon_sessions, Number(c.last_close), c.sessions_elapsed);
    expect(st.target).toBeCloseTo(c.expected.target, 9);
    expect(st.earnings).toBeCloseTo(c.expected.earnings, 9);
    expect(st.daily).toBeCloseTo(c.expected.daily, 9);
    expect(st.weekly).toBeCloseTo(c.expected.weekly, 9);
    expect(ck.progress).toBeCloseTo(c.expected.progress, 9);
    expect([ck.targetReached, ck.timeElapsed]).toEqual([c.expected.target_reached, c.expected.time_elapsed]);
  });

  it("reproduces the document example", () => {
    const st = salesTarget(23.13, 30, 20);
    expect(st.target.toFixed(2)).toBe("30.07");
    expect(st.earnings.toFixed(2)).toBe("6.94");
    expect(st.daily.toFixed(3)).toBe("0.347");
  });
});
