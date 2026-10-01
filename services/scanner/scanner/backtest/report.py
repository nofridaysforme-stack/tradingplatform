"""Backtest report (spec 12): report.html, trades.csv, settings.json. For the owners'
internal use only. The HTML is self-contained (no external files) and follows the
viewer's light or dark setting."""

import csv
import html
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scanner.backtest.engine import EngineResult, SimTrade
from scanner.backtest.metrics import (
    MIN_SAMPLE,
    Metrics,
    equity_curve,
    indicator_frequency,
    monthly,
    split,
)

STRATEGY_NAMES = {"three_eight": "3/8 Formula", "fib_pivot": "Fibonacci Pivot"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TRADE_FIELDS = [
    "strategy", "instrument", "direction", "bar_ts", "trading_day", "sample", "entry", "stop",
    "target", "alt_target", "risk_pips", "reward_pips", "reward_risk", "indicator_count",
    "fired", "has_provisional", "is_countertrend", "range_mode", "state", "closed_at",
    "exit_price", "gross_pips", "net_pips", "events", "explanation", "dedupe_key", "version_set",
]  # fmt: skip


@dataclass
class PairRun:
    result: EngineResult
    start: datetime
    end: datetime

    def by_strategy(self) -> dict[str, list[SimTrade]]:
        out: dict[str, list[SimTrade]] = {}
        for t in self.result.trades:
            out.setdefault(t.signal.strategy, []).append(t)
        return out


def write(out_dir: Path, runs: Sequence[PairRun], settings: dict[str, Any], title: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_trades(out_dir / "trades.csv", runs)
    (out_dir / "settings.json").write_text(json.dumps(settings, indent=2, default=str))
    page = out_dir / "report.html"
    page.write_text(render(runs, settings, title))
    return page


def write_trades(path: Path, runs: Sequence[PairRun]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TRADE_FIELDS)
        w.writeheader()
        for run in runs:
            cut = run.start + (run.end - run.start) * 0.7
            for t in run.result.trades:
                s = t.signal
                w.writerow({
                    "strategy": s.strategy, "instrument": s.instrument, "direction": s.direction,
                    "bar_ts": s.bar_ts.isoformat(), "trading_day": s.trading_day.isoformat(),
                    "sample": "in" if s.bar_ts < cut else "out", "entry": s.entry, "stop": s.stop,
                    "target": s.target, "alt_target": s.alt_target, "risk_pips": s.risk_pips,
                    "reward_pips": s.reward_pips, "reward_risk": s.reward_risk,
                    "indicator_count": s.indicator_count,
                    "fired": ";".join(i.key for i in s.indicators if i.fired),
                    "has_provisional": s.has_provisional, "is_countertrend": s.is_countertrend,
                    "range_mode": s.range_mode, "state": t.state,
                    "closed_at": t.closed_at.isoformat() if t.closed_at else "",
                    "exit_price": t.exit_price, "gross_pips": t.gross_pips, "net_pips": t.net_pips,
                    "events": ";".join(t.events), "explanation": s.explanation,
                    "dedupe_key": s.dedupe_key, "version_set": json.dumps(s.version_set),
                })  # fmt: skip


# HTML


def _fmt(value: object, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    return html.escape(str(value))


def _metrics_row(label: str, m: Metrics) -> str:
    pf = _fmt(m.profit_factor, 2)
    flag = "" if m.enough_trades else f'<span class="warn">under {MIN_SAMPLE} trades</span>'
    sign = "pos" if m.net_pips > 0 else "neg" if m.net_pips < 0 else ""
    return (
        f"<tr><th scope='row'>{label}{flag}</th><td class='num'>{m.trades}</td>"
        f"<td class='num'>{m.win_rate * 100:.1f}%</td><td class='num'>{_fmt(m.avg_win)}</td>"
        f"<td class='num'>{_fmt(m.avg_loss)}</td><td class='num {sign}'>{_fmt(m.expectancy, 2)}</td>"
        f"<td class='num'>{pf}</td><td class='num {sign}'>{_fmt(m.net_pips)}</td>"
        f"<td class='num'>{_fmt(m.max_drawdown)}</td><td class='num'>{m.longest_losing_streak}</td>"
        f"<td class='num'>{_fmt(m.planned_rr, 2)} / {_fmt(m.achieved_rr, 2)}</td>"
        f"<td class='num'>{_fmt(m.trades_per_week, 2)}</td></tr>"
    )


METRIC_HEAD = (
    "<thead><tr><th>Sample</th><th class='num'>Trades</th><th class='num'>Win rate</th>"
    "<th class='num'>Avg win</th><th class='num'>Avg loss</th><th class='num'>Expectancy</th>"
    "<th class='num'>Profit factor</th><th class='num'>Net pips</th><th class='num'>Max drawdown</th>"
    "<th class='num'>Losing streak</th><th class='num'>R planned / achieved</th>"
    "<th class='num'>Trades per week</th></tr></thead>"
)


def _chart(points: list[tuple[datetime, float]], start: datetime, end: datetime, cut: datetime,
           label: str) -> str:  # fmt: skip
    """Cumulative pips (line) and drawdown (filled area below zero), split marker at 70%."""
    w, h, pad_l, pad_r, pad_t, pad_b = 720, 220, 56, 12, 12, 26
    if not points:
        return "<p class='muted'>No closed trades.</p>"
    span = (end - start).total_seconds() or 1.0
    vals = [v for _, v in points]
    peak, dds = 0.0, []
    for v in vals:
        peak = max(peak, v)
        dds.append(v - peak)
    lo, hi = min([0.0, *vals, *dds]), max([0.0, *vals])
    rng = (hi - lo) or 1.0

    def x(t: datetime) -> float:
        return pad_l + (w - pad_l - pad_r) * (t - start).total_seconds() / span

    def y(v: float) -> float:
        return pad_t + (h - pad_t - pad_b) * (hi - v) / rng

    line = " ".join(f"{x(t):.1f},{y(v):.1f}" for t, v in [(start, 0.0), *points])
    dd = " ".join(f"{x(t):.1f},{y(d):.1f}" for (t, _), d in zip(points, dds, strict=True))
    dd_area = f"{x(points[0][0]):.1f},{y(0):.1f} {dd} {x(points[-1][0]):.1f},{y(0):.1f}"
    cx = x(cut)
    return f"""<svg viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(label)}">
<line x1="{pad_l}" x2="{w - pad_r}" y1="{y(0):.1f}" y2="{y(0):.1f}" class="axis"/>
<polygon points="{dd_area}" class="dd"/>
<polyline points="{line}" class="eq"/>
<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{pad_t}" y2="{h - pad_b}" class="cut"/>
<text x="{cx + 4:.1f}" y="{pad_t + 10}" class="lbl">out of sample</text>
<text x="{pad_l - 6}" y="{y(hi) + 4:.1f}" class="lbl" text-anchor="end">{hi:,.0f}</text>
<text x="{pad_l - 6}" y="{y(0) + 4:.1f}" class="lbl" text-anchor="end">0</text>
<text x="{pad_l - 6}" y="{y(lo) + 4:.1f}" class="lbl" text-anchor="end">{lo:,.0f}</text>
<text x="{pad_l}" y="{h - 6}" class="lbl">{start:%Y-%m}</text>
<text x="{w - pad_r}" y="{h - 6}" class="lbl" text-anchor="end">{end:%Y-%m}</text>
</svg>"""


def _monthly_grid(trades: list[SimTrade]) -> str:
    grid = monthly(trades)
    if not grid:
        return ""
    years = sorted({k[:4] for k in grid})
    head = "".join(f"<th class='num'>{m}</th>" for m in MONTHS)
    body = ""
    for yr in years:
        cells = ""
        total = 0.0
        for mi in range(1, 13):
            v = grid.get(f"{yr}-{mi:02d}")
            if v is None:
                cells += "<td></td>"
                continue
            total += v
            cls = "pos" if v > 0 else "neg" if v < 0 else ""
            cells += f"<td class='num {cls}'>{v:,.0f}</td>"
        cls = "pos" if total > 0 else "neg" if total < 0 else ""
        body += f"<tr><th scope='row'>{yr}</th>{cells}<td class='num {cls}'><b>{total:,.0f}</b></td></tr>"
    return f"<div class='scroll'><table class='grid'><thead><tr><th>Year</th>{head}<th class='num'>Year</th></tr></thead><tbody>{body}</tbody></table></div>"


def _indicator_table(trades: list[SimTrade]) -> str:
    rows = indicator_frequency(trades)
    if not rows:
        return ""
    body = "".join(
        f"<tr><th scope='row'>{html.escape(r['name'])}"
        f"{' <span class=prov>provisional</span>' if r['provisional'] else ''}</th>"
        f"<td class='num'>{r['fired']}</td><td class='num'>{r['share_of_trades'] * 100:.0f}%</td>"
        f"<td class='num'>{_fmt(r['win_rate_when_fired'] and r['win_rate_when_fired'] * 100)}"
        f"{'%' if r['win_rate_when_fired'] is not None else ''}</td>"
        f"<td class='num'>{_fmt(r['expectancy_when_fired'], 2)}</td></tr>"
        for r in rows
    )
    return (
        "<h4>Indicator frequency in taken trades</h4><div class='scroll'><table><thead><tr>"
        "<th>Indicator</th><th class='num'>Fired</th><th class='num'>Share of trades</th>"
        "<th class='num'>Win rate when fired</th><th class='num'>Expectancy when fired</th>"
        f"</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _costs_text(costs: dict[str, dict[str, float]]) -> str:
    return "; ".join(
        f"{pair} spread {c['spread_pips']} pips, slippage {c['slippage_pips']} pips"
        for pair, c in costs.items()
    )


def render(runs: Sequence[PairRun], settings: dict[str, Any], title: str) -> str:
    sections = []
    summary_rows = ""
    rejections: Counter[str] = Counter()
    outside = 0
    for run in runs:
        rejections.update(run.result.rejections)
        outside += run.result.outside_window
        for strategy, trades in run.by_strategy().items():
            ins, outs, cut = split(trades, run.start, run.end)
            name = f"{run.result.instrument}, {STRATEGY_NAMES.get(strategy, strategy)}"
            summary_rows += _metrics_row(f"{html.escape(name)} (out of sample)", outs)
            sections.append(f"""<section><h3>{html.escape(name)}</h3>
<div class='scroll'><table>{METRIC_HEAD}<tbody>{_metrics_row("In sample (first 70%)", ins)}{_metrics_row("Out of sample (last 30%)", outs)}</tbody></table></div>
<figure>{_chart(equity_curve(trades), run.start, run.end, cut, name)}<figcaption>Cumulative net pips (line) and drawdown (shaded). The marker shows where the out-of-sample period starts.</figcaption></figure>
<h4>Monthly net pips</h4>{_monthly_grid(trades)}
{_indicator_table(trades) if strategy == "three_eight" else ""}</section>""")
    rej_rows = "".join(
        f"<tr><th scope='row'>{html.escape(k)}</th><td class='num'>{v:,}</td></tr>"
        for k, v in rejections.most_common()
    )
    changed = settings.get("changed") or {}
    changed_html = (
        "".join(
            f"<li><code>{html.escape(k)}</code>: {html.escape(json.dumps(v))}</li>"
            for k, v in changed.items()
        )
        or "<li>None: rules exactly as loaded</li>"
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ --bg:#f5f6f4; --surface:#fff; --fg:#1c2128; --muted:#5d6672; --line:#d6dad6;
  --long:#2457c5; --short:#b06a00; --pos:#1f6f43; --neg:#a4332a; --prov:#6d4fc2; color-scheme: light; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#1b2027; --surface:#232a33; --fg:#e6e9ee;
  --muted:#9aa4b1; --line:#36404c; --long:#7fa6f5; --short:#f0b04a; --pos:#6fcf97; --neg:#f28b82;
  --prov:#b39cf5; color-scheme: dark; }} }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; padding:24px 16px 64px; }}
main {{ max-width:1100px; margin:0 auto; display:grid; gap:28px; }}
h1 {{ font-size:1.6rem; margin:0; }} h2 {{ font-size:1.2rem; margin:0 0 8px; }} h3 {{ font-size:1.05rem; margin:0 0 8px; }} h4 {{ font-size:.9rem; margin:16px 0 6px; }}
section {{ background:var(--surface); border:1px solid var(--line); border-radius:6px; padding:16px; min-width:0; }}
table {{ border-collapse:collapse; width:100%; font-size:.85rem; }}
th, td {{ text-align:left; padding:5px 8px; border-bottom:1px solid var(--line); vertical-align:top; }}
thead th {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
.pos {{ color:var(--pos); }} .neg {{ color:var(--neg); }} .muted, figcaption {{ color:var(--muted); font-size:.8rem; }}
th[scope=row] {{ white-space:nowrap; }}
.warn {{ display:block; color:var(--short); font-size:.72rem; font-weight:600; }} .prov {{ color:var(--prov); font-size:.72rem; border:1px dashed var(--prov); padding:0 4px; border-radius:3px; }}
.scroll {{ overflow-x:auto; }} figure {{ margin:12px 0 0; }} svg {{ width:100%; height:auto; }}
svg .eq {{ fill:none; stroke:var(--long); stroke-width:1.6; }} svg .dd {{ fill:var(--neg); opacity:.18; }}
svg .axis {{ stroke:var(--line); }} svg .cut {{ stroke:var(--muted); stroke-dasharray:4 3; }}
svg .lbl {{ fill:var(--muted); font-size:11px; }} code {{ font-size:.8rem; }}
table.grid td, table.grid th {{ padding:4px 6px; }}
</style></head><body><main>
<header><p class="muted">Backtest · internal use only</p><h1>{html.escape(title)}</h1>
<p class="muted">{html.escape(str(settings.get("start")))} to {html.escape(str(settings.get("end")))} · costs: {html.escape(_costs_text(settings.get("costs") or {}))} · results in pips, net of costs. A bar that touches both stop and target counts as a loss.</p></header>
<section><h2>Summary (out of sample)</h2><p class="muted">The final 30 percent of the period. Settings were compared only on the first 70 percent. Fewer than {MIN_SAMPLE} trades is too few to draw conclusions.</p>
<div class='scroll'><table>{METRIC_HEAD}<tbody>{summary_rows}</tbody></table></div></section>
{"".join(sections)}
<section><h2>Rejection reasons</h2><p class="muted">How often each gate rejected a candidate (a candidate can fail several). {outside:,} bars fell outside every trading window and were not evaluated.</p>
<div class='scroll'><table><thead><tr><th>Gate</th><th class='num'>Rejections</th></tr></thead><tbody>{rej_rows}</tbody></table></div></section>
<section><h2>Settings used</h2><ul>{changed_html}</ul><p class="muted">Full version set and parameters: settings.json. Every trade: trades.csv.</p></section>
</main></body></html>"""
