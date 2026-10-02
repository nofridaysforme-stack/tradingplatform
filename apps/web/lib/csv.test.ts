import { describe, expect, it } from "vitest";
import { csvCell, csvLine } from "./csv";

describe("csv", () => {
  it("quotes commas, quotes, and line breaks", () => {
    expect(csvCell('a,"b"')).toBe('"a,""b"""');
    expect(csvCell("x\ny")).toBe('"x\ny"');
  });

  it("neutralises text that would run as a formula", () => {
    expect(csvCell("=HYPERLINK(1)")).toBe("'=HYPERLINK(1)");
    expect(csvCell("@cmd")).toBe("'@cmd");
  });

  it("keeps numbers, including negatives, as numbers", () => {
    expect(csvLine([-12.5, 41, true, null, "EUR/USD"])).toBe("-12.5,41,true,,EUR/USD");
  });
});
