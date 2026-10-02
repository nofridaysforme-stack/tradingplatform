"""Synthetic M15 random walk plus D/W/M candles aggregated on the 17:00 New York roll."""

from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from scanner.time import is_forex_open, trading_day_of, trading_day_start


def make(
    days: int = 60,
    seed: int = 1,
    start: datetime = datetime(2026, 1, 5, 0, 0, tzinfo=UTC),
    base: float = 1.10,
    vol: float = 0.00035,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    rows = []
    p = base
    t = start
    end = start + timedelta(days=days)
    while t < end:
        if is_forex_open(t + timedelta(minutes=14)):
            steps = p + np.cumsum(rng.normal(0, vol / 2, 4))
            o = p
            c = steps[-1]
            hi = max(o, steps.max()) + abs(rng.normal(0, vol / 4))
            lo = min(o, steps.min()) - abs(rng.normal(0, vol / 4))
            rows.append((t, o, hi, lo, c))
            p = c
        t += timedelta(minutes=15)
    m15 = pd.DataFrame(rows, columns=["ts", "o", "h", "l", "c"])
    m15["ts"] = pd.to_datetime(m15["ts"], utc=True)
    m15["day"] = [trading_day_of(x.to_pydatetime()) for x in m15["ts"]]
    g = (
        m15.groupby("day")
        .agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"))
        .reset_index()
    )
    g["ts"] = [trading_day_start(d) for d in g["day"]]
    daily = g[["ts", "o", "h", "l", "c"]].copy()
    daily["ts"] = pd.to_datetime(daily["ts"], utc=True)

    def agg(key: Any) -> pd.DataFrame:
        g2 = g.copy()
        g2["k"] = g2["day"].map(key)
        a = (
            g2.groupby("k")
            .agg(
                ts=("ts", "first"),
                o=("o", "first"),
                h=("h", "max"),
                l=("l", "min"),
                c=("c", "last"),
            )
            .reset_index(drop=True)
        )
        a["ts"] = pd.to_datetime(a["ts"], utc=True)
        return a

    weekly = agg(lambda d: d.isocalendar()[:2])
    monthly = agg(lambda d: (d.year, d.month))
    return m15[["ts", "o", "h", "l", "c"]], daily, weekly, monthly
