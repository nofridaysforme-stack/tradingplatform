"""Cost model (spec 12). Results are measured on mid prices, then costs are taken off.

- Spread: paid once per trade (half on entry, half on exit). From the selected broker
  profile's typical spread for the pair; otherwise 1.0 pip on majors, 1.5 on USD/JPY.
- Slippage: 0.5 pip on entry and again on a stop exit (stops fill as market orders).
- A bar that touches both stop and target counts as a stop hit (handled by the lifecycle).
"""

from dataclasses import dataclass

MAJORS_AT_ONE_PIP = frozenset({"EUR/USD", "GBP/USD", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD"})
MAJOR_SPREAD = 1.0
OTHER_SPREAD = 1.5  # USD/JPY and every other pair
SLIPPAGE = 0.5
STOP_EXITS = frozenset({"stop_hit", "ambiguous"})


@dataclass(frozen=True)
class CostModel:
    spread_pips: float
    slippage_pips: float = SLIPPAGE

    def cost_pips(self, exit_state: str) -> float:
        slips = 2 if exit_state in STOP_EXITS else 1
        return self.spread_pips + self.slippage_pips * slips

    def net(self, gross_pips: float, exit_state: str) -> float:
        return round(gross_pips - self.cost_pips(exit_state), 2)


def default_spread(symbol: str) -> float:
    return MAJOR_SPREAD if symbol in MAJORS_AT_ONE_PIP else OTHER_SPREAD
