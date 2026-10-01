"""Backtest metrics (spec 12), all on results net of costs, in pips.

Validation split: the first 70 percent of the period is in-sample (for comparing settings);
the final 30 percent is out-of-sample and is the real result.
"""

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from scanner.backtest.engine import SimTrade

IN_SAMPLE_SHARE = 0.7
MIN_SAMPLE = 100  # spec 12: no conclusions from fewer trades


@dataclass
class Metrics:
    trades: int = 0
    wins: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    expectancy: float = 0.0
    profit_factor: float | None = None
    net_pips: float = 0.0
    max_drawdown: float = 0.0
    longest_losing_streak: int = 0
    planned_rr: float = 0.0
    achieved_rr: float = 0.0
    trades_per_week: float = 0.0
    by_state: dict[str, int] = field(default_factory=dict)
    enough_trades: bool = False

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def closed_trades(trades: Sequence[SimTrade]) -> list[SimTrade]:
    out = [t for t in trades if t.closed and t.state != "invalidated" and t.net_pips is not None]
    return sorted(out, key=lambda t: (t.closed_at or t.signal.bar_ts, t.signal.dedupe_key))


def compute(trades: Sequence[SimTrade], start: datetime, end: datetime) -> Metrics:
    closed = closed_trades(trades)
    m = Metrics(trades=len(closed))
    if not closed:
        return m
    nets = [float(t.net_pips or 0.0) for t in closed]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    m.wins = sum(1 for t in closed if t.state == "target_hit")
    m.win_rate = round(m.wins / len(closed), 4)
    m.avg_win = round(sum(wins) / len(wins), 2) if wins else 0.0
    m.avg_loss = round(sum(losses) / len(losses), 2) if losses else 0.0
    m.expectancy = round(sum(nets) / len(nets), 2)
    gross_loss = -sum(losses)
    m.profit_factor = round(sum(wins) / gross_loss, 2) if gross_loss > 0 else None
    m.net_pips = round(sum(nets), 1)

    peak = cum = 0.0
    drawdown = 0.0
    streak = longest = 0
    for x in nets:
        cum += x
        peak = max(peak, cum)
        drawdown = max(drawdown, peak - cum)
        streak = streak + 1 if x <= 0 else 0
        longest = max(longest, streak)
    m.max_drawdown = round(drawdown, 1)
    m.longest_losing_streak = longest

    m.planned_rr = round(sum(t.signal.reward_risk for t in closed) / len(closed), 2)
    achieved = [
        float(t.gross_pips or 0.0) / t.signal.risk_pips for t in closed if t.signal.risk_pips
    ]
    m.achieved_rr = round(sum(achieved) / len(achieved), 2) if achieved else 0.0
    weeks = max((end - start).days / 7, 1 / 7)
    m.trades_per_week = round(len(closed) / weeks, 2)
    m.by_state = dict(Counter(t.state for t in closed))
    m.enough_trades = len(closed) >= MIN_SAMPLE
    return m


def split_point(start: datetime, end: datetime) -> datetime:
    return start + (end - start) * IN_SAMPLE_SHARE


def split(
    trades: Sequence[SimTrade], start: datetime, end: datetime
) -> tuple[Metrics, Metrics, datetime]:
    cut = split_point(start, end)
    ins = [t for t in trades if t.signal.bar_ts < cut]
    outs = [t for t in trades if t.signal.bar_ts >= cut]
    return compute(ins, start, cut), compute(outs, cut, end), cut


def equity_curve(trades: Sequence[SimTrade]) -> list[tuple[datetime, float]]:
    cum = 0.0
    points = []
    for t in closed_trades(trades):
        cum += float(t.net_pips or 0.0)
        points.append((t.closed_at or t.signal.bar_ts, round(cum, 1)))
    return points


def monthly(trades: Sequence[SimTrade]) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for t in closed_trades(trades):
        when = t.closed_at or t.signal.bar_ts
        out[f"{when.year}-{when.month:02d}"] += float(t.net_pips or 0.0)
    return {k: round(v, 1) for k, v in sorted(out.items())}


def indicator_frequency(trades: Sequence[SimTrade]) -> list[dict[str, Any]]:
    """For 3/8 trades: how often each indicator fired, and the win rate when it did. The key
    input for approving provisional rules (spec 12)."""
    closed = [t for t in closed_trades(trades) if t.signal.strategy == "three_eight"]
    stats: dict[str, dict[str, Any]] = {}
    for t in closed:
        for ind in t.signal.indicators:
            row = stats.setdefault(
                ind.key, {"key": ind.key, "name": ind.name, "provisional": ind.provisional,
                          "fired": 0, "wins_when_fired": 0, "net_when_fired": 0.0},
            )  # fmt: skip
            if ind.fired:
                row["fired"] += 1
                row["wins_when_fired"] += t.state == "target_hit"
                row["net_when_fired"] += float(t.net_pips or 0.0)
    out = []
    for row in stats.values():
        fired = row["fired"]
        out.append({
            **row,
            "share_of_trades": round(fired / len(closed), 3) if closed else 0.0,
            "win_rate_when_fired": round(row["wins_when_fired"] / fired, 3) if fired else None,
            "expectancy_when_fired": round(row["net_when_fired"] / fired, 2) if fired else None,
        })  # fmt: skip
    return out
