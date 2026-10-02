// Forex pair conventions for the "Add pair" form (CLAUDE.md rule 6: pips come from the
// instrument). Yen-quoted pairs move in 0.01; the rest in 0.0001.

export const PIP_SIZES = ["0.0001", "0.01"] as const;
export type PipSize = (typeof PIP_SIZES)[number];

export function normalizePair(raw: string): string | null {
  const s = raw.trim().toUpperCase().replace(/[\s_\-]/g, "/").replace(/^([A-Z]{3})([A-Z]{3})$/, "$1/$2");
  return /^[A-Z]{3}\/[A-Z]{3}$/.test(s) && s.slice(0, 3) !== s.slice(4) ? s : null;
}

export function defaultPipSize(symbol: string): PipSize {
  return symbol.endsWith("/JPY") ? "0.01" : "0.0001";
}

/** Prices show one digit beyond the pip (fractional pips), like the seeded pairs. */
export function displayDecimals(pip: PipSize): number {
  return pip === "0.01" ? 3 : 5;
}

export const providerCode = (symbol: string) => symbol.replace("/", "_");
