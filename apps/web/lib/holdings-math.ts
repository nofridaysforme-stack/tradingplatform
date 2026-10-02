/**
 * Sales targets (spec 08, Entry Points and Sales Targets). Mirrors sales_target and
 * check_holding in services/scanner/scanner/strategies/stock_screener.py; both are tested
 * against services/scanner/tests/fixtures/holding_cases.json. Display only: the worker sends
 * the holding alerts.
 */
export interface SalesTarget {
  target: number;
  earnings: number;
  daily: number;
  weekly: number;
}

export function salesTarget(purchasePrice: number, expectedProfitPct: number, horizonSessions: number): SalesTarget {
  const target = purchasePrice * (1 + expectedProfitPct / 100);
  const earnings = target - purchasePrice;
  const daily = earnings / horizonSessions;
  return { target, earnings, daily, weekly: daily * 5 };
}

export interface HoldingCheck {
  progress: number;
  sessionsElapsed: number;
  targetReached: boolean;
  timeElapsed: boolean;
}

export function checkHolding(
  purchasePrice: number,
  expectedProfitPct: number,
  horizonSessions: number,
  lastClose: number,
  sessionsElapsed: number,
): HoldingCheck {
  const st = salesTarget(purchasePrice, expectedProfitPct, horizonSessions);
  const reached = lastClose >= st.target;
  return {
    progress: (lastClose - purchasePrice) / st.earnings,
    sessionsElapsed,
    targetReached: reached,
    timeElapsed: !reached && sessionsElapsed >= horizonSessions,
  };
}
