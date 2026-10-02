import { describe, expect, it } from "vitest";
import { parseTheme } from "./theme";

describe("parseTheme", () => {
  it("accepts the three themes", () => {
    expect(parseTheme("light")).toBe("light");
    expect(parseTheme("dark")).toBe("dark");
    expect(parseTheme("device")).toBe("device");
  });

  it("falls back to the device setting for anything else", () => {
    expect(parseTheme(undefined)).toBe("device");
    expect(parseTheme("blue")).toBe("device");
  });
});
