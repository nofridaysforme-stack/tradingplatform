import type { Direction } from "@/lib/db/schema";

/**
 * Broker adjustment (spec 10). Signals are computed on mid prices; each owner's view shifts
 * the levels by half their broker's typical spread. This mirrors
 * services/scanner/scanner/signals/broker_adjust.py, and both are tested against
 * services/scanner/tests/fixtures/broker_adjust_cases.json. It changes how a signal is shown,
 * never whether it fires.
 */
export interface Adjusted {
  entry: number;
  stop: number;
  target: number;
  rewardRisk: number;
}

const round = (value: number, decimals: number) => Number(value.toFixed(decimals));

export function adjust(
  direction: Direction,
  entry: number,
  stop: number,
  target: number,
  typicalSpreadPips: number,
  pipSize: number,
  decimals = 5,
): Adjusted {
  const half = (typicalSpreadPips / 2) * pipSize;
  const [e, s, t] =
    direction === "long" ? [entry + half, stop - half, target - half] : [entry - half, stop + half, target + half];
  const risk = Math.abs(e - s);
  const ratio = risk ? Math.abs(t - e) / risk : 0;
  return { entry: round(e, decimals), stop: round(s, decimals), target: round(t, decimals), rewardRisk: round(ratio, 3) };
}

/** "Open in broker" link (spec 10): {symbol} is the broker's symbol override, or the display
 *  symbol without the slash. */
export function brokerLink(template: string | null, symbol: string, override: string | null): string | null {
  if (!template) return null;
  const url = template.replaceAll("{symbol}", encodeURIComponent(override ?? symbol.replace("/", "")));
  return /^https:\/\//.test(url) ? url : null;
}
