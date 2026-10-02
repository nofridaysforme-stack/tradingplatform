import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { adjust, brokerLink } from "./broker-adjust";

interface Case {
  direction: "long" | "short";
  entry: number;
  stop: number;
  target: number;
  typical_spread_pips: number;
  pip_size: number;
  decimals: number;
  expected: { entry: number; stop: number; target: number; reward_risk: number };
}

const FIXTURE = path.resolve(__dirname, "../../../services/scanner/tests/fixtures/broker_adjust_cases.json");
const { cases } = JSON.parse(readFileSync(FIXTURE, "utf8")) as { cases: Case[] };

describe("adjust", () => {
  it.each(cases)("matches the scanner for a $direction at $entry", (c) => {
    const a = adjust(c.direction, c.entry, c.stop, c.target, c.typical_spread_pips, c.pip_size, c.decimals);
    expect(a.entry).toBeCloseTo(c.expected.entry, 9);
    expect(a.stop).toBeCloseTo(c.expected.stop, 9);
    expect(a.target).toBeCloseTo(c.expected.target, 9);
    expect(a.rewardRisk).toBeCloseTo(c.expected.reward_risk, 9);
  });
});

describe("brokerLink", () => {
  it("fills the symbol without the slash", () => {
    expect(brokerLink("https://trade.example.com/?s={symbol}", "EUR/USD", null)).toBe("https://trade.example.com/?s=EURUSD");
  });

  it("prefers the broker's own symbol", () => {
    expect(brokerLink("https://t.example.com/{symbol}", "EUR/USD", "EURUSD.m")).toBe("https://t.example.com/EURUSD.m");
  });

  it("has no link without a template or for a non-https address", () => {
    expect(brokerLink(null, "EUR/USD", null)).toBeNull();
    expect(brokerLink("javascript:alert({symbol})", "EUR/USD", null)).toBeNull();
  });
});
