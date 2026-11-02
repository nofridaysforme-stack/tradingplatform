"""Chart series for the stock page (spec 13): the indicator lines the portal draws under the
candles. They come from the same indicator code as the buy and sell votes
(strategies/stock_momentum.py), so the chart never shows a cross the scanner did not count
(CLAUDE.md rule 1). The portal only draws them.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

import numpy as np
import talib

from scanner.rules.registry import RuleSet
from scanner.strategies import stock_momentum as sm
from scanner.strategies.stock_screener import DayBar, high_low_52w

# Sessions kept for the chart: up to about five years, so the page can zoom out over all the
# history the screen loads (jobs/stock_eod.py HISTORY_DAYS). It opens on the last six months.
CHART_SESSIONS = 1300
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


def _periods(bars: Sequence[DayBar], period: str) -> list[DayBar]:
    """Daily bars combined into weekly or monthly bars, each dated by its last session. The
    latest period may still be running."""
    out: list[DayBar] = []
    last_key: tuple[int, int] | None = None
    for b in bars:
        d = b.session_date
        key = (d.isocalendar()[0], d.isocalendar()[1]) if period == "weekly" else (d.year, d.month)
        if key != last_key:
            out.append(b if b.o is not None else replace(b, o=b.c))
            last_key = key
            continue
        p = out[-1]
        out[-1] = DayBar(d, max(p.h, b.h), min(p.l, b.l), b.c, p.volume + b.volume, p.o)
    return out


def _lines(
    bars: Sequence[DayBar], fired: dict[str, sm.Fired], rules: RuleSet, n: int
) -> dict[str, Any]:
    """The indicator lines over the last n bars."""
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
        "pivot_ma": values("stocks.ind_pivot", "pivot_ma"),
        "pivot_signal": values("stocks.ind_pivot", "signal"),
    }


def _period_view(bars: Sequence[DayBar], period: str, rules: RuleSet) -> dict[str, Any]:
    """Weekly or monthly candles with the same indicators and settings, counted in weeks or
    months. For reading the bigger picture only: the votes are on daily bars (spec 08)."""
    agg = _periods(bars, period)
    n = min(CHART_SESSIONS, len(agg))
    view = _lines(agg, sm.indicators(agg, rules), rules, n)
    view["bars"] = [
        {
            "time": b.session_date.isoformat(),
            "open": float(b.o if b.o is not None else b.c),
            "high": float(b.h),
            "low": float(b.l),
            "close": float(b.c),
            "volume": b.volume,
        }
        for b in agg[-n:]
    ]
    return view


def chart_series(
    bars: Sequence[DayBar], fired: dict[str, sm.Fired], rules: RuleSet
) -> dict[str, Any]:
    """The lines, levels, and votes for the last CHART_SESSIONS bars, and the same lines on
    weekly and monthly bars. A switched-off indicator has no lines (null)."""
    n = min(CHART_SESSIONS, len(bars))
    high, _ = high_low_52w(bars, rules)
    ratio = float(rules.params("stocks.rule1_near_high")["ratio"])
    rsi_p = rules.params("stocks.ind_rsi")
    stoch_p = rules.params("stocks.ind_stoch")
    macd_p = rules.params("stocks.ind_macd")
    return {
        **_lines(bars, fired, rules, n),
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
        "weekly": _period_view(bars, "weekly", rules),
        "monthly": _period_view(bars, "monthly", rules),
    }
