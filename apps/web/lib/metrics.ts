// History summary metrics, with the same definitions as the backtest
// (services/scanner/scanner/backtest/metrics.py): wins are target hits, losses are results of
// zero or less, profit factor is gross wins over gross losses (none without losses).
// Live results are on reference prices, before any broker spread.

export interface Trade {
  state: string;
  resultPips: number;
}

export interface Summary {
  trades: number;
  wins: number;
  winRate: number;
  netPips: number;
  expectancy: number;
  profitFactor: number | null;
}

const round = (v: number, d: number) => Math.round(v * 10 ** d) / 10 ** d;

export function summarize(trades: Trade[]): Summary {
  const closed = trades.filter((t) => t.state !== "invalidated");
  if (closed.length === 0) return { trades: 0, wins: 0, winRate: 0, netPips: 0, expectancy: 0, profitFactor: null };
  const nets = closed.map((t) => t.resultPips);
  const gains = nets.filter((x) => x > 0).reduce((a, b) => a + b, 0);
  const grossLoss = -nets.filter((x) => x <= 0).reduce((a, b) => a + b, 0);
  const wins = closed.filter((t) => t.state === "target_hit").length;
  const net = nets.reduce((a, b) => a + b, 0);
  return {
    trades: closed.length,
    wins,
    winRate: round(wins / closed.length, 4),
    netPips: round(net, 1),
    expectancy: round(net / closed.length, 2),
    profitFactor: grossLoss > 0 ? round(gains / grossLoss, 2) : null,
  };
}

/** Running total of pips in close order, for the cumulative chart. */
export function cumulative(trades: (Trade & { closedAt: string })[]): { at: string; pips: number }[] {
  let total = 0;
  return trades
    .filter((t) => t.state !== "invalidated")
    .map((t) => {
      total = round(total + t.resultPips, 1);
      return { at: t.closedAt, pips: total };
    });
}
