import { describe, expect, it } from "vitest";
import type { WorkerMarket } from "./db/schema";
import { healthReasons } from "./health-status";

const NOW = new Date("2026-10-07T13:30:00Z");
const MARKET: WorkerMarket = {
  at: NOW.toISOString(),
  forex_open: true,
  trading_day: "2026-10-07",
  window_enabled: true,
  window: "primary",
  windows: [],
  in_window: true,
  next_open: null,
  stale: [],
};

describe("healthReasons", () => {
  it("is healthy with a fresh heartbeat and no stale pairs", () => {
    expect(healthReasons({ dbOk: true, heartbeatAt: NOW, market: MARKET, now: NOW })).toEqual([]);
  });

  it("reports an old or missing heartbeat", () => {
    const old = new Date(NOW.getTime() - 6 * 60_000);
    expect(healthReasons({ dbOk: true, heartbeatAt: old, market: MARKET, now: NOW })).toEqual(["heartbeat_stale"]);
    expect(healthReasons({ dbOk: true, heartbeatAt: null, market: null, now: NOW })).toEqual(["heartbeat_stale"]);
  });

  it("reports stale pairs only while forex is open", () => {
    const stale = { ...MARKET, stale: ["GBP/USD"] };
    expect(healthReasons({ dbOk: true, heartbeatAt: NOW, market: stale, now: NOW })).toEqual(["pairs_stale"]);
    expect(healthReasons({ dbOk: true, heartbeatAt: NOW, market: { ...stale, forex_open: false }, now: NOW })).toEqual([]);
  });

  it("does not check pairs while forex is paused", () => {
    const market = { ...MARKET, forex_open: true, stale: ["GBP/USD"] };
    expect(healthReasons({ dbOk: true, heartbeatAt: NOW, market, now: NOW, forex: false })).toEqual([]);
  });

  it("reports only the database when it is unreachable", () => {
    expect(healthReasons({ dbOk: false, heartbeatAt: null, market: null, now: NOW })).toEqual(["database_unreachable"]);
  });
});
