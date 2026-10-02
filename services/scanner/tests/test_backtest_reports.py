import csv
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from scanner.backtest import run as run_cli
from scanner.backtest import sweeps
from scanner.backtest.engine import SimTrade
from scanner.backtest.metrics import compute, indicator_frequency, monthly, split
from scanner.backtest.stocks import hit_rate, summarize
from scanner.backtest.stocks import write as write_stocks
from scanner.rules.registry import UnknownRuleError, derive
from scanner.strategies import three_eight
from scanner.strategies.stock_screener import DayBar
from tests.conftest import FIXTURES, load_fixture, ruleset_from_snapshot
from tests.strategy_kit import context
from tests.synth import make

RULES = ruleset_from_snapshot()
T0 = datetime(2026, 1, 5, tzinfo=UTC)


def trade(net: float, state: str, days: int, gross: float | None = None) -> SimTrade:
    draft = three_eight.evaluate(context(load_fixture("eurusd_worked_example.json"))).signals[0]
    draft = draft.model_copy(update={"bar_ts": T0 + timedelta(days=days)})
    return SimTrade(draft, state=state, closed_at=T0 + timedelta(days=days, hours=2),
                    gross_pips=gross if gross is not None else net + 1.5, net_pips=net)  # fmt: skip


def test_metrics_by_hand() -> None:
    trades = [
        trade(60, "target_hit", 1),
        trade(-25, "stop_hit", 2),
        trade(-25, "ambiguous", 3),
        trade(60, "target_hit", 4),
        trade(5, "expired", 5),
        SimTrade(trade(0, "open", 6).signal),
    ]
    m = compute(trades, T0, T0 + timedelta(days=14))
    assert m.trades == 5 and m.wins == 2 and m.win_rate == 0.4
    assert m.net_pips == 75.0 and m.expectancy == 15.0
    assert m.avg_win == pytest.approx(41.67, abs=0.01) and m.avg_loss == -25.0
    assert m.profit_factor == 2.5
    assert m.max_drawdown == 50.0 and m.longest_losing_streak == 2
    assert m.trades_per_week == 2.5 and not m.enough_trades
    assert m.by_state == {"target_hit": 2, "stop_hit": 1, "ambiguous": 1, "expired": 1}
    assert monthly(trades) == {"2026-01": 75.0}
    ins, outs, cut = split(trades, T0, T0 + timedelta(days=10))
    assert cut == T0 + timedelta(days=7) and ins.trades == 5 and outs.trades == 0
    freq = {r["key"]: r for r in indicator_frequency(trades)}
    assert freq["three_eight.pivot_touch"]["fired"] == 5
    assert freq["three_eight.pivot_touch"]["win_rate_when_fired"] == 0.4
    assert freq["three_eight.hl_failure"]["fired"] == 0


def test_derive_changes_only_this_run() -> None:
    changed = derive(RULES, {"three_eight.target": {"daily_target_max_pips": 50}},
                     {"three_eight.flag_pennant_triangle"})  # fmt: skip
    assert changed.params("three_eight.target")["daily_target_max_pips"] == 50
    assert not changed.enabled("three_eight.flag_pennant_triangle")
    assert RULES.params("three_eight.target")["daily_target_max_pips"] == 75
    with pytest.raises(UnknownRuleError):
        derive(RULES, {"three_eight.nope": {"x": 1}})


@pytest.fixture(scope="module")
def cache(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("cache")
    m15, daily, weekly, monthly_df = make(days=30)
    for gran, df in (("M15", m15), ("D", daily), ("W", weekly), ("M", monthly_df)):
        folder = root / "EUR_USD" / gran
        folder.mkdir(parents=True)
        df.to_parquet(folder / "2026.parquet", index=False)
    return root


def test_run_cli_writes_the_report(cache: Path, tmp_path: Path) -> None:
    out = tmp_path / "report"
    run_cli.main([
        "--strategy", "both", "--pairs", "EUR/USD", "--start", "2026-01-05", "--end", "2026-02-04",
        "--report", str(out), "--rules-file", str(FIXTURES / "rules_snapshot.json"),
        "--cache", str(cache), "--offline", "--workers", "1",
        "--set", "three_eight.target.daily_target_max_pips=60",
        "--disable", "three_eight.flag_pennant_triangle",
    ])  # fmt: skip
    page = (out / "report.html").read_text()
    assert "Summary (out of sample)" in page and "EUR/USD, 3/8 Formula" in page and "<svg" in page
    settings = json.loads((out / "settings.json").read_text())
    assert settings["changed"]["three_eight.target"] == {"daily_target_max_pips": 60}
    assert settings["params"]["three_eight.flag_pennant_triangle"]["enabled"] is False
    assert settings["costs"]["EUR/USD"] == {"spread_pips": 1.0, "slippage_pips": 0.5}
    rows = list(csv.DictReader((out / "trades.csv").open()))
    assert rows and {r["sample"] for r in rows} <= {"in", "out"}
    assert all(r["instrument"] == "EUR/USD" for r in rows)


def test_sweeps_cli(cache: Path, tmp_path: Path) -> None:
    out = tmp_path / "sweeps"
    sweeps.main([
        "--only", "baseline,target_max_50", "--pairs", "EUR/USD", "--start", "2026-01-05",
        "--end", "2026-02-04", "--report", str(out), "--rules-file",
        str(FIXTURES / "rules_snapshot.json"), "--cache", str(cache), "--offline", "--workers", "1",
    ])  # fmt: skip
    assert (out / "baseline" / "report.html").exists() and (
        out / "target_max_50" / "trades.csv"
    ).exists()
    rows = list(csv.DictReader((out / "summary.csv").open()))
    assert {r["config"] for r in rows} == {"baseline", "target_max_50"}
    assert {r["sample"] for r in rows} == {"in", "out"}


def test_cli_needs_data_access() -> None:
    with pytest.raises(SystemExit, match="DATABASE_URL"):
        run_cli.main(["--report", "/tmp/x", "--offline"])


def _stock(ticker: str, path: list[float], start: date = date(2024, 1, 1)) -> list[DayBar]:
    out, d = [], start
    for c in path:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        p = Decimal(str(round(c, 4)))
        out.append(DayBar(d, p * Decimal("1.01"), p * Decimal("0.99"), p, 500_000))
        d += timedelta(days=1)
    return out


def test_stock_hit_rate(tmp_path: Path) -> None:
    rise = [3 + 6 * k / 259 for k in range(260)]
    winner = _stock("WIN", [*rise, *[9 * (1 + 0.04 * k) for k in range(1, 25)]])
    loser = _stock("LOSE", [*rise, *[9.0] * 24])
    picks = hit_rate({"WIN": winner, "LOSE": loser}, RULES)
    first = {p.ticker: p for p in sorted(picks, key=lambda p: p.session, reverse=True)}
    assert any(p.ticker == "WIN" and p.hit for p in picks)
    assert first["LOSE"].hit in (False, None)
    s = summarize(picks)
    assert s["picks"] == len(picks) and 0 <= s["hit_rate"] <= 1
    write_stocks(tmp_path, picks)
    assert "excludes companies that later delisted" in (tmp_path / "stock_report.html").read_text()
