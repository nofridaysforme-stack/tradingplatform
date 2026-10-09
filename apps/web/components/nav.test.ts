import { describe, expect, it } from "vitest";
import { navItems } from "./nav";

const hrefs = (forex: boolean, mobile: boolean) => navItems(forex, mobile).map((i) => i.href);

describe("navItems", () => {
  it("shows every page while forex is on, with five mobile tabs", () => {
    expect(hrefs(true, false)).toEqual(["/dashboard", "/levels", "/stocks", "/holdings", "/history", "/econ", "/health", "/settings"]);
    expect(hrefs(true, true)).toEqual(["/dashboard", "/levels", "/stocks", "/history", "/settings"]);
  });

  it("hides the forex pages while forex is paused, and gives Holdings a mobile tab", () => {
    expect(hrefs(false, false)).toEqual(["/stocks", "/holdings", "/health", "/settings"]);
    expect(hrefs(false, true)).toEqual(["/stocks", "/holdings", "/settings"]);
  });
});
