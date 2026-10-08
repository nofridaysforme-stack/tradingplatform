import { describe, expect, it } from "vitest";
import type { WorkerMarket } from "./db/schema";
import { marketView } from "./market";

const NOW = new Date("2026-10-07T13:42:00Z"); // 09:42 New York
const OPEN: WorkerMarket = {
  at: NOW.toISOString(),
  forex_open: true,
  trading_day: "2026-10-07",
  window_enabled: true,
  window: "primary",
  windows: [{ start: "00:00", end: "10:30" }],
  in_window: true,
  next_open: null,
  stale: [],
};

describe("marketView", () => {
  it("shows the open market and the window end", () => {
    expect(marketView(NOW, OPEN, NOW)).toEqual({
      health: "ok",
      line: "Forex open · In 3/8 window until 10:30 · 09:42 NY",
      stale: [],
    });
  });

  it("shows outside the window and a switched-off window", () => {
    expect(marketView(NOW, { ...OPEN, in_window: false }, NOW).line).toContain("Outside 3/8 window");
    expect(marketView(NOW, { ...OPEN, window_enabled: false, in_window: false }, NOW).line).toContain("3/8 window off");
  });

  it("shows the next open time when closed, with no window", () => {
    const closed = { ...OPEN, forex_open: false, in_window: false, next_open: "2026-10-11T21:00:00Z" };
    expect(marketView(NOW, closed, NOW).line).toBe("Forex closed · Opens Sunday 17:00 NY · 09:42 NY");
  });

  it("warns about stale pairs", () => {
    const v = marketView(NOW, { ...OPEN, stale: ["GBP/USD"] }, NOW);
    expect(v.health).toBe("warn");
    expect(v.stale).toEqual(["GBP/USD"]);
  });

  it("is unknown when the heartbeat is old or missing", () => {
    expect(marketView(new Date(NOW.getTime() - 6 * 60_000), OPEN, NOW).health).toBe("down");
    expect(marketView(null, null, NOW).health).toBe("down");
  });

  it("shows forex as paused, and still a late scanner", () => {
    expect(marketView(NOW, null, NOW, false)).toEqual({ health: "ok", line: "Forex paused · 09:42 NY", stale: [] });
    expect(marketView(NOW, { ...OPEN, stale: ["GBP/USD"] }, NOW, false).stale).toEqual([]);
    expect(marketView(new Date(NOW.getTime() - 6 * 60_000), null, NOW, false).health).toBe("down");
  });
});
