import { describe, expect, it } from "vitest";
import { nyLocalToUtc, toNyLocal } from "./ny-time";

describe("New York local time", () => {
  it("converts in daylight time and standard time", () => {
    expect(nyLocalToUtc("2026-10-07T08:30")?.toISOString()).toBe("2026-10-07T12:30:00.000Z");
    expect(nyLocalToUtc("2026-12-04T08:30")?.toISOString()).toBe("2026-12-04T13:30:00.000Z");
  });

  it("round-trips", () => {
    expect(toNyLocal(new Date("2026-10-07T12:30:00Z"))).toBe("2026-10-07T08:30");
  });

  it("refuses malformed values and the skipped spring-forward hour", () => {
    expect(nyLocalToUtc("2026-10-07 08:30")).toBeNull();
    expect(nyLocalToUtc("2026-13-07T08:30")).toBeNull();
    expect(nyLocalToUtc("2027-03-14T02:30")).toBeNull();
  });
});
