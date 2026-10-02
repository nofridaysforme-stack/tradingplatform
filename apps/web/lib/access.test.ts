import { describe, expect, it } from "vitest";
import { IpLimiter, normalizeEmail } from "./access";

describe("normalizeEmail", () => {
  it("trims and lowercases", () => {
    expect(normalizeEmail("  Admin@Example.COM ")).toBe("admin@example.com");
  });
});

describe("IpLimiter", () => {
  it("allows up to the limit within the window", () => {
    const limiter = new IpLimiter(3, 1000);
    expect([0, 1, 2, 3].map((t) => limiter.allow("1.2.3.4", t))).toEqual([true, true, true, false]);
  });

  it("counts each address separately", () => {
    const limiter = new IpLimiter(1, 1000);
    expect(limiter.allow("1.1.1.1", 0)).toBe(true);
    expect(limiter.allow("2.2.2.2", 0)).toBe(true);
    expect(limiter.allow("1.1.1.1", 1)).toBe(false);
  });

  it("allows again once old requests leave the window", () => {
    const limiter = new IpLimiter(2, 1000);
    limiter.allow("ip", 0);
    limiter.allow("ip", 500);
    expect(limiter.allow("ip", 999)).toBe(false);
    expect(limiter.allow("ip", 1000)).toBe(true);
  });
});
