// Names for the stock system's indicators and events (spec 08). Shared by pages and tests.

export const INDICATORS = ["stocks.ind_candle", "stocks.ind_macd", "stocks.ind_pivot", "stocks.ind_rsi", "stocks.ind_stoch"] as const;

export const INDICATOR_NAMES: Record<string, string> = {
  "stocks.ind_candle": "Change in direction candle",
  "stocks.ind_macd": "MACD crossover",
  "stocks.ind_pivot": "Pivot point crossover",
  "stocks.ind_rsi": "RSI",
  "stocks.ind_stoch": "Stochastics",
};

/** What each indicator's buy and sell mean, in the words of the rule (defaults). */
export const INDICATOR_RULES: Record<string, { buy: string; sell: string }> = {
  "stocks.ind_candle": { buy: "Close above the previous session's high", sell: "Close below the previous session's low" },
  "stocks.ind_macd": { buy: "MACD line crosses above its signal line", sell: "MACD line crosses below its signal line" },
  "stocks.ind_pivot": { buy: "Pivot line hooks above its 3-day average", sell: "Pivot line hooks below its 3-day average" },
  "stocks.ind_rsi": { buy: "RSI crosses above the buy level", sell: "RSI crosses below the sell level" },
  "stocks.ind_stoch": { buy: "Stochastics %K crosses above the buy level", sell: "%K crosses below the sell level" },
};

export const VALUE_NAMES: Record<string, string> = {
  close: "Close",
  previous_high: "Previous high",
  previous_low: "Previous low",
  macd: "MACD",
  signal: "Signal",
  pivot: "Pivot",
  average: "3-day average",
  rsi: "RSI",
  k: "%K",
  d: "%D",
};

export const EVENT_NAMES: Record<string, string> = {
  bought: "Bought",
  trailing_started: "Trailing stop started",
  projection_reached: "Projection reached",
  horizon_passed: "Horizon passed",
  stopped: "Stopped out",
  trailing_stopped: "Trailing stop hit",
  sold: "Sell signal",
};

/** The candle vote's name: buys before 2026-10-29 voted on candle patterns, stored with it. */
export function indicatorName(key: string, patterns?: string[]): string {
  if (key === "stocks.ind_candle" && patterns?.length) return "Price and candle";
  return INDICATOR_NAMES[key] ?? key;
}

export function patternName(p: string): string {
  return p.replaceAll("_", " ");
}
