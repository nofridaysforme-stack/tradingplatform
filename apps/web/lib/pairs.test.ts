import { describe, expect, it } from "vitest";
import { defaultPipSize, displayDecimals, normalizePair, providerCode } from "./pairs";

describe("pairs", () => {
  it("normalizes the ways people type a pair", () => {
    expect(normalizePair("eur/gbp")).toBe("EUR/GBP");
    expect(normalizePair("EURGBP")).toBe("EUR/GBP");
    expect(normalizePair(" gbp-jpy ")).toBe("GBP/JPY");
    expect(normalizePair("EUR/EUR")).toBeNull();
    expect(normalizePair("EURO/USD")).toBeNull();
  });

  it("fills the pip size and decimals from the quote currency", () => {
    expect(defaultPipSize("GBP/JPY")).toBe("0.01");
    expect(defaultPipSize("EUR/GBP")).toBe("0.0001");
    expect(displayDecimals("0.01")).toBe(3);
    expect(displayDecimals("0.0001")).toBe(5);
    expect(providerCode("EUR/GBP")).toBe("EUR_GBP");
  });
});
