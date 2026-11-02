"""Chart series for the stock page (spec 13): the indicator lines the portal draws under the
candles. They come from the same indicator code as the buy and sell votes
(strategies/stock_momentum.py), so the chart never shows a cross the scanner did not count
(CLAUDE.md rule 1). The portal only draws them.
"""

from collections.abc import Sequence
from typing import Any

import numpy as np
import talib

from scanner.rules.registry import RuleSet
from scanner.strategies import stock_momentum as sm
from scanner.strategies.stock_screener import DayBar, high_low_52w

# Sessions kept for the chart: about six months, the span the stock page shows.
CHART_SESSIONS = 130
# The 50-session average is drawn for the longer trend; it is not part of any vote.
TREND_SESSIONS = 50


def _list(values: sm.Floats, n: int) -> list[float | None]:
    """The last n values, rounded, with NaN as None."""
    out: list[float | None] = []
    for v in np.asarray(values, dtype=np.float64)[-n:]:
        out.append(None if np.isnan(v) else round(float(v), 6))
    return out


def _dates(bars: Sequence[DayBar], flags: sm.Flags, n: int) -> list[str]:
    start = len(bars) - n
    return [bars[start + i].session_date.isoformat() for i, f in enumerate(flags[-n:]) if f]


def chart_series(
    bars: Sequence[DayBar], fired: dict[str, sm.Fired], rules: RuleSet
) -> dict[str, Any]:
    """The lines, levels, and votes for the last CHART_SESSIONS bars. A switched-off indicator
    has no lines (null)."""
    n = min(CHART_SESSIONS, len(bars))
    closes = np.array([float(b.c) for b in bars], dtype=np.float64)

    def values(key: str, name: str) -> list[float | None] | None:
        f = fired.get(key)
        return _list(f.values[name], n) if f is not None else None

    ma: dict[str, list[float | None]] = {}
    lengths: list[int] = []
    if "stocks.ind_ma" in fired:
        p = rules.params("stocks.ind_ma")
        lengths = [int(p["short_sessions"]), int(p["long_sessions"])]
        ma[str(lengths[0])] = _list(fired["stocks.ind_ma"].values["short"], n)
        ma[str(lengths[1])] = _list(fired["stocks.ind_ma"].values["long"], n)
    if TREND_SESSIONS not in lengths and len(closes) >= TREND_SESSIONS:
        ma[str(TREND_SESSIONS)] = _list(talib.SMA(closes, timeperiod=TREND_SESSIONS), n)

    macd = values("stocks.ind_macd", "macd")
    signal = values("stocks.ind_macd", "signal")
    histogram = (
        [
            None if a is None or b is None else round(a - b, 6)
            for a, b in zip(macd, signal, strict=True)
        ]
        if macd is not None and signal is not None
        else None
    )
    high, _ = high_low_52w(bars, rules)
    ratio = float(rules.params("stocks.rule1_near_high")["ratio"])
    rsi_p = rules.params("stocks.ind_rsi")
    stoch_p = rules.params("stocks.ind_stoch")
    macd_p = rules.params("stocks.ind_macd")
    return {
        "sessions": [b.session_date.isoformat() for b in bars[-n:]],
        "ma": ma,
        "volume_average": values("stocks.ind_volume", "average_volume"),
        "rsi": values("stocks.ind_rsi", "rsi"),
        "stoch_k": values("stocks.ind_stoch", "k"),
        "stoch_d": values("stocks.ind_stoch", "d"),
        "macd": macd,
        "macd_signal": signal,
        "macd_histogram": histogram,
        "levels": {
            "high_52w": float(high),
            "zone_low": round(float(high) * ratio, 6),
            "rsi": [float(rsi_p["buy_level"]), float(rsi_p["sell_level"])],
            "stoch": [float(stoch_p["buy_level"]), float(stoch_p["sell_level"])],
        },
        "settings": {
            "rsi": int(rsi_p["period"]),
            "stoch": [
                int(stoch_p["k_period"]),
                int(stoch_p["k_slowing"]),
                int(stoch_p["d_period"]),
            ],
            "macd": [int(macd_p["fast"]), int(macd_p["slow"]), int(macd_p["signal"])],
        },
        "votes": {
            key: {"buy": _dates(bars, f.buy, n), "sell": _dates(bars, f.sell, n)}
            for key, f in fired.items()
        },
    }
