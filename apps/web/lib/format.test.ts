import { describe, expect, it } from "vitest";
import { age, money, nyDayTime, nyTime, percent, pips, price, ratio } from "./format";

describe("format", () => {
  it("shows prices at the instrument's decimals", () => {
    expect(price("1.08420000", 5)).toBe("1.08420");
    expect(price("149.5200", 3)).toBe("149.520");
    expect(price(null, 5)).toBe("");
  });

  it("signs pips", () => {
    expect(pips("41.00")).toBe("+41");
    expect(pips(-12.5)).toBe("-12.5");
    expect(pips(0)).toBe("0");
  });

  it("rounds reward to risk", () => {
    expect(ratio("2.740")).toBe("2.74");
  });

  it("uses New York time across daylight saving", () => {
    expect(nyTime(new Date("2026-10-07T13:30:00Z"))).toBe("09:30");
    expect(nyTime(new Date("2026-12-07T14:30:00Z"))).toBe("09:30");
    expect(nyDayTime(new Date("2026-10-11T21:00:00Z"))).toBe("Sunday 17:00");
  });

  it("describes age", () => {
    const now = new Date("2026-10-07T13:30:00Z");
    expect(age(new Date("2026-10-07T13:29:30Z"), now)).toBe("Just now");
    expect(age(new Date("2026-10-07T13:18:00Z"), now)).toBe("12 min ago");
    expect(age(new Date("2026-10-07T10:00:00Z"), now)).toBe("3 h ago");
    expect(age(new Date("2026-10-05T13:00:00Z"), now)).toBe("2 days ago");
  });

  it("formats stock figures", () => {
    expect(percent(0.392207)).toBe("39.2%");
    expect(percent(20.3948)).toBe("2,039%");
    expect(percent(-0.05)).toBe("-5%");
    expect(percent(null)).toBe("");
    expect(money(30.069)).toBe("30.07");
  });
});
