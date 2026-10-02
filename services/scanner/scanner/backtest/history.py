"""Historical candles from OANDA, cached as Parquet (spec 12).

One file per instrument, granularity, and year under the cache directory. Complete past
years are fetched once; the current year is refetched on each run. Only completed candles
are kept. Prices are mid, aligned to the 17:00 New York day like the live worker.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import pandas as pd

from scanner.data.base import Candle, completed

log = logging.getLogger(__name__)

DEFAULT_CACHE = Path(__file__).resolve().parents[2] / ".cache" / "history"
COLUMNS = ["ts", "o", "h", "l", "c"]


class HistorySource(Protocol):
    def history(
        self, instrument: str, granularity: str, start: datetime, end: datetime | None = None
    ) -> list[Candle]: ...


def _frame(candles: list[Candle]) -> pd.DataFrame:
    rows = [(c.ts, float(c.o), float(c.h), float(c.l), float(c.c)) for c in completed(candles)]
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def load(
    source: HistorySource | None,
    instrument: str,
    granularity: str,
    start: datetime,
    end: datetime,
    cache_dir: Path = DEFAULT_CACHE,
    now: datetime | None = None,
) -> pd.DataFrame:
    """Candles with start <= ts < end, oldest first. With source=None, cached data only."""
    now = now or datetime.now(UTC)
    folder = cache_dir / instrument / granularity
    folder.mkdir(parents=True, exist_ok=True)
    frames = []
    for year in range(start.year, end.year + 1):
        path = folder / f"{year}.parquet"
        current = year >= now.year
        if path.exists() and not current:
            frames.append(pd.read_parquet(path))
            continue
        if source is None:
            if path.exists():
                frames.append(pd.read_parquet(path))
            continue
        y0 = datetime(year, 1, 1, tzinfo=UTC)
        y1 = min(datetime(year + 1, 1, 1, tzinfo=UTC), now)
        df = _frame(source.history(instrument, granularity, y0, y1))
        df.to_parquet(path, index=False)
        log.info("history cached", extra={"instrument": instrument, "granularity": granularity,
                                          "year": year, "candles": len(df)})  # fmt: skip
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.concat(frames, ignore_index=True).drop_duplicates("ts").sort_values("ts")
    mask = (df["ts"] >= pd.Timestamp(start)) & (df["ts"] < pd.Timestamp(end))
    return df.loc[mask].reset_index(drop=True)
