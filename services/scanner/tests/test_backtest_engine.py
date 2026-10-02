from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
import pytest

from scanner.backtest import history
from scanner.backtest.costs import CostModel, default_spread
from scanner.backtest.engine import EngineResult, levels_from_history, rows_of, run_pair
from scanner.data.base import Candle
from scanner.instruments import Instrument
from scanner.strategies.common import InstrumentRef
from scanner.time import trading_day_start
from tests.conftest import ruleset_from_snapshot
from tests.synth import make

RULES = ruleset_from_snapshot()
INST = Instrument(id=uuid4(), symbol="EUR/USD", provider_code="EUR_USD",
                  pip_size=Decimal("0.0001"), display_decimals=5)  # fmt: skip
REF = InstrumentRef(INST.id, INST.symbol, 0.0001, 5)


Frames = tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]


@pytest.fixture(scope="module")
def synth() -> Frames:
    return make(days=30)


def run(frames: Frames, m15: pd.DataFrame | None = None, **kw: Any) -> EngineResult:
    bars, daily, weekly, monthly = frames
    lf = levels_from_history(INST, daily, weekly, monthly, RULES)
    return run_pair(REF, bars if m15 is None else m15, lf, RULES, CostModel(1.0), **kw)


def opened_before(res: EngineResult, cutoff: datetime) -> list[tuple[str, float, float, float]]:
    return [
        (t.signal.dedupe_key, t.signal.entry, t.signal.stop, t.signal.target)
        for t in res.trades
        if t.signal.bar_ts < cutoff
    ]


def keys(res: EngineResult) -> list[str]:
    return [t.signal.dedupe_key for t in res.trades]


def test_engine_produces_trades_and_rejection_counts(synth: Frames) -> None:
    res = run(synth)
    assert res.trades and res.evaluated > 0 and res.outside_window > 0
    assert sum(res.rejections.values()) > 0
    closed = [t for t in res.trades if t.closed]
    assert closed and all(t.net_pips is not None for t in closed)
    for t in closed:
        cost = 1.0 + 0.5 * (2 if t.state in ("stop_hit", "ambiguous") else 1)
        assert t.net_pips == pytest.approx((t.gross_pips or 0) - cost)


def test_no_look_ahead(synth: Frames) -> None:
    """Trades opened before a cutoff are identical whether or not later bars exist."""
    m15 = synth[0]
    cutoff = m15["ts"].iloc[len(m15) * 2 // 3].to_pydatetime()
    full = run(synth)
    part = run(synth, m15[m15["ts"] < cutoff])
    assert opened_before(full, cutoff) == opened_before(part, cutoff)
    assert opened_before(part, cutoff)


def test_skipping_closed_windows_changes_no_signal(synth: Frames) -> None:
    fast = run(synth)
    slow = run(synth, skip_outside_window=False)
    assert keys(fast) == keys(slow)
    assert slow.outside_window == 0 and slow.evaluated > fast.evaluated


def test_levels_use_only_the_prior_day(synth: Frames) -> None:
    _, daily, weekly, monthly = synth
    lf = levels_from_history(INST, daily, weekly, monthly, RULES)
    rows = rows_of(daily)
    day = date(2026, 1, 14)  # a Wednesday
    prior = next(r for r in rows if r[0] == trading_day_start(date(2026, 1, 13)))
    sets = lf(day)
    assert sets["prev_day"]["PDH"] == pytest.approx(prior[2], abs=1e-8)
    assert sets["daily"]["source"]["ts"] == prior[0].isoformat()
    assert "weekly" in sets


def test_costs() -> None:
    assert default_spread("EUR/USD") == 1.0
    assert default_spread("USD/JPY") == 1.5
    assert default_spread("EUR/GBP") == 1.5
    model = CostModel(1.2)
    assert model.net(20.0, "target_hit") == 18.3
    assert model.net(-23.0, "stop_hit") == -25.2
    assert model.net(-23.0, "ambiguous") == -25.2
    assert model.net(4.0, "expired") == 2.3


class FakeHistory:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, datetime]] = []

    def history(self, instrument: str, granularity: str, start: datetime,
                end: datetime | None = None) -> list[Candle]:  # fmt: skip
        self.calls.append((instrument, granularity, start))
        return [
            Candle(
                instrument=instrument,
                granularity=granularity,
                ts=start + timedelta(days=k),
                o=Decimal("1.1"),
                h=Decimal("1.2"),
                l=Decimal("1.0"),
                c=Decimal("1.15"),
                volume=1,
                complete=k < 3,
            )
            for k in range(4)
        ]


def test_history_cache(tmp_path: Path) -> None:
    src = FakeHistory()
    now = datetime(2026, 6, 1, tzinfo=UTC)
    start, end = datetime(2024, 1, 1, tzinfo=UTC), datetime(2026, 6, 1, tzinfo=UTC)
    df = history.load(src, "EUR_USD", "D", start, end, tmp_path, now)
    assert len(src.calls) == 3 and len(df) == 9  # incomplete candles dropped
    history.load(src, "EUR_USD", "D", start, end, tmp_path, now)
    assert len(src.calls) == 4  # past years from cache; only the current year refetched
    cached = history.load(None, "EUR_USD", "D", start, end, tmp_path, now)
    assert len(cached) == 9
    assert (tmp_path / "EUR_USD" / "D" / "2024.parquet").exists()
