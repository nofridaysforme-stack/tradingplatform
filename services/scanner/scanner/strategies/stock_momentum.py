"""Stock momentum system (spec 08, revised 2026-10-08 and 2026-10-20). Pure functions over
daily bars.

    qualified (stock_screener.screen) -> 10-week momentum on the week's close -> watch list
    -> buy vote -> hold -> exit

The live job (jobs/stock_eod.py) and the backtest (backtest/stocks.py) both call these, so a
buy or an exit is decided by the same code in both.
"""

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from functools import cache
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
import talib

from scanner.rules.registry import RuleSet
from scanner.strategies.stock_screener import DayBar, ScreenResult, in_zone, screen
from scanner.time import us_stock_holidays

K = "stocks."
INDICATORS = (
    "stocks.ind_candle",
    "stocks.ind_macd",
    "stocks.ind_pivot",
    "stocks.ind_rsi",
    "stocks.ind_stoch",
)
Side = Literal["buy", "sell"]
Floats = npt.NDArray[np.float64]
Flags = npt.NDArray[np.bool_]

# TA-Lib functions by the names used in stocks.ind_candle. TA-Lib returns a positive value for
# a bullish completion and a negative one for a bearish completion.
PATTERNS: dict[str, Callable[..., Any]] = {
    "hammer": talib.CDLHAMMER,
    "inverted_hammer": talib.CDLINVERTEDHAMMER,
    "engulfing": talib.CDLENGULFING,
    "piercing": talib.CDLPIERCING,
    "morning_star": talib.CDLMORNINGSTAR,
    "harami": talib.CDLHARAMI,
    "dragonfly_doji": talib.CDLDRAGONFLYDOJI,
    "dark_cloud_cover": talib.CDLDARKCLOUDCOVER,
    "hanging_man": talib.CDLHANGINGMAN,
    "shooting_star": talib.CDLSHOOTINGSTAR,
    "evening_star": talib.CDLEVENINGSTAR,
}


# Indicators


@dataclass(frozen=True)
class Fired:
    """One indicator over every session: where its buy and sell conditions became true, and
    the values behind them. Index i is bars[i]."""

    buy: Flags
    sell: Flags
    values: dict[str, Floats]
    buy_names: list[list[str]] = field(default_factory=list)  # candle patterns only
    sell_names: list[list[str]] = field(default_factory=list)


def _arrays(bars: Sequence[DayBar]) -> tuple[Floats, Floats, Floats, Floats]:
    c = np.array([float(b.c) for b in bars], dtype=np.float64)
    o = np.array([float(b.o) if b.o is not None else float("nan") for b in bars], dtype=np.float64)
    h = np.array([float(b.h) for b in bars], dtype=np.float64)
    low = np.array([float(b.l) for b in bars], dtype=np.float64)
    return o, h, low, c


def cross_above(a: Floats, b: Floats) -> Flags:
    """True where a was at or below b on the previous session and is above it now."""
    out = np.zeros(len(a), dtype=np.bool_)
    if len(a) > 1:
        with np.errstate(invalid="ignore"):
            out[1:] = (a[:-1] <= b[:-1]) & (a[1:] > b[1:])
    return out


def cross_below(a: Floats, b: Floats) -> Flags:
    out = np.zeros(len(a), dtype=np.bool_)
    if len(a) > 1:
        with np.errstate(invalid="ignore"):
            out[1:] = (a[:-1] >= b[:-1]) & (a[1:] < b[1:])
    return out


def _level(n: int, value: float) -> Floats:
    return np.full(n, value, dtype=np.float64)


def candle(bars: Sequence[DayBar], params: dict[str, Any]) -> Fired:
    """stocks.ind_candle. The pullback-zone condition for a buy is applied in buy_votes."""
    o, h, low, c = _arrays(bars)
    n = len(c)
    buy_names: list[list[str]] = [[] for _ in range(n)]
    sell_names: list[list[str]] = [[] for _ in range(n)]
    if n and not np.isnan(o).any():
        for name in params["bullish"]:
            out = PATTERNS[name](o, h, low, c)
            for i in np.nonzero(out > 0)[0]:
                buy_names[i].append(name)
        for name in params["bearish"]:
            out = PATTERNS[name](o, h, low, c)
            for i in np.nonzero(out < 0)[0]:
                sell_names[i].append(name)
    buy = np.array([bool(x) for x in buy_names], dtype=np.bool_)
    sell = np.array([bool(x) for x in sell_names], dtype=np.bool_)
    return Fired(buy, sell, {}, buy_names, sell_names)


def macd(bars: Sequence[DayBar], params: dict[str, Any]) -> Fired:
    _, _, _, c = _arrays(bars)
    line, signal, _hist = talib.MACD(
        c,
        fastperiod=int(params["fast"]),
        slowperiod=int(params["slow"]),
        signalperiod=int(params["signal"]),
    )
    return Fired(
        cross_above(line, signal), cross_below(line, signal), {"macd": line, "signal": signal}
    )


def pivot(bars: Sequence[DayBar], params: dict[str, Any]) -> Fired:
    _, h, low, c = _arrays(bars)
    line = (h + low + c) / 3
    n = int(params["average_sessions"])
    avg = talib.SMA(line, timeperiod=n) if len(line) >= n else np.full(len(line), np.nan)
    return Fired(cross_above(line, avg), cross_below(line, avg), {"pivot": line, "average": avg})


def rsi(bars: Sequence[DayBar], params: dict[str, Any]) -> Fired:
    _, _, _, c = _arrays(bars)
    values = talib.RSI(c, timeperiod=int(params["period"]))
    n = len(c)
    buy = cross_above(values, _level(n, float(params["buy_level"])))
    sell = cross_below(values, _level(n, float(params["sell_level"])))
    return Fired(buy, sell, {"rsi": values})


def stoch(bars: Sequence[DayBar], params: dict[str, Any]) -> Fired:
    _, h, low, c = _arrays(bars)
    # Simple moving averages for the slowing and %D, TA-Lib's default.
    k, d = talib.STOCH(
        h,
        low,
        c,
        fastk_period=int(params["k_period"]),
        slowk_period=int(params["k_slowing"]),
        slowd_period=int(params["d_period"]),
    )
    n = len(c)
    buy = cross_above(k, _level(n, float(params["buy_level"])))
    sell = cross_below(k, _level(n, float(params["sell_level"])))
    return Fired(buy, sell, {"k": k, "d": d})


COMPUTE: dict[str, Callable[[Sequence[DayBar], dict[str, Any]], Fired]] = {
    "stocks.ind_candle": candle,
    "stocks.ind_macd": macd,
    "stocks.ind_pivot": pivot,
    "stocks.ind_rsi": rsi,
    "stocks.ind_stoch": stoch,
}


def indicators(bars: Sequence[DayBar], rules: RuleSet) -> dict[str, Fired]:
    """Every enabled indicator over the whole history. A switched-off indicator never fires."""
    return {key: COMPUTE[key](bars, rules.params(key)) for key in INDICATORS if rules.enabled(key)}


# Votes


@dataclass(frozen=True)
class Vote:
    key: str
    index: int  # the latest session in the window where it fired
    names: tuple[str, ...] = ()  # candle patterns


def votes(
    bars: Sequence[DayBar],
    fired: dict[str, Fired],
    i: int,
    side: Side,
    window: int,
    rules: RuleSet,
    after: int = -1,
) -> list[Vote]:
    """The indicators that fired on the given side within the window ending at session i, only
    on sessions after `after` (an entry). A bullish candle counts only inside the pullback
    zone (spec 08: bullish candles on support)."""
    out: list[Vote] = []
    first = max(after + 1, i - window + 1, 0)
    for key, f in fired.items():
        flags = f.buy if side == "buy" else f.sell
        for j in range(i, first - 1, -1):
            if not flags[j]:
                continue
            if key == "stocks.ind_candle" and side == "buy" and not in_zone(bars[: j + 1], rules):
                continue
            names = f.buy_names if side == "buy" else f.sell_names
            out.append(Vote(key, j, tuple(names[j]) if names else ()))
            break
    return out


def vote_passes(found: Sequence[Vote], rule_key: str, rules: RuleSet) -> bool:
    return rules.enabled(rule_key) and len(found) >= int(rules.params(rule_key)["min_votes"])


def window_of(rule_key: str, rules: RuleSet) -> int:
    return int(rules.params(rule_key)["window_sessions"])


# The week's close and the 10-week momentum ladder

# True when the US stock market holds a session on the date.
IsOpen = Callable[[date], bool]


def us_sessions(closures: Collection[date] = ()) -> IsOpen:
    """The NYSE calendar: weekdays except the standing holidays and the extra closures in
    market_holidays."""
    extra = frozenset(closures)
    holidays = cache(us_stock_holidays)

    def is_open(d: date) -> bool:
        return d.weekday() < 5 and d not in extra and d not in holidays(d.year)

    return is_open


def is_week_close(session: date, is_open: IsOpen) -> bool:
    """The week's last session: the Friday, or the session before a closed Friday (spec 08:
    when the market is closed on the Friday, the Thursday close stands in)."""
    d = session + timedelta(days=1)
    while d.weekday() < 5:
        if is_open(d):
            return False
        d += timedelta(days=1)
    return True


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_close_back(bars: Sequence[DayBar], i: int, weeks: int) -> int | None:
    """The index of the last session of the week `weeks` weeks before bars[i]'s week; None
    when that week has no stored session."""
    start = _monday(bars[i].session_date) - timedelta(weeks=weeks)
    end = start + timedelta(days=7)
    for k in range(i - 1, -1, -1):
        d = bars[k].session_date
        if d < start:
            return None
        if d < end:
            return k
    return None


def momentum_threshold(rules: RuleSet) -> Decimal:
    """projection / horizon x trader year: 0.35 / 20 x 260 = 4.55 at the defaults."""
    p = rules.params(K + "momentum")
    trader_year = int(rules.params(K + "five_line")["trader_year"])
    return Decimal(str(p["projection_pct"])) / 100 / int(p["horizon_sessions"]) * trader_year


@dataclass(frozen=True)
class Rung:
    """One week back: (week close - that week's close) / that close / days x trader year."""

    weeks: int
    days: int
    session: date | None
    close: Decimal | None
    rate: Decimal | None
    passed: bool


@dataclass(frozen=True)
class Ladder:
    session: date
    close: Decimal
    rungs: tuple[Rung, ...]
    threshold: Decimal
    needed: int

    @property
    def passes(self) -> int:
        return sum(r.passed for r in self.rungs)

    @property
    def passed(self) -> bool:
        return self.passes >= self.needed


def ladder(bars: Sequence[DayBar], i: int, rules: RuleSet) -> Ladder:
    """The 10-week ladder from session i's close (spec 08 Stage 2): for each of 1 to `weeks`
    weeks back, the rate from that week's close, with `days_per_week` days a week."""
    p = rules.params(K + "momentum")
    trader_year = int(rules.params(K + "five_line")["trader_year"])
    threshold = momentum_threshold(rules)
    c0 = bars[i].c
    rungs: list[Rung] = []
    for w in range(1, int(p["weeks"]) + 1):
        days = w * int(p["days_per_week"])
        k = week_close_back(bars, i, w)
        if k is None or bars[k].c <= 0:
            rungs.append(Rung(w, days, None, None, None, False))
            continue
        low = bars[k].c
        rate = (c0 - low) / low / days * trader_year
        rungs.append(Rung(w, days, bars[k].session_date, low, rate, rate >= threshold))
    return Ladder(bars[i].session_date, c0, tuple(rungs), threshold, int(p["min_weeks_passing"]))


def passes_momentum(bars: Sequence[DayBar], rules: RuleSet, is_open: IsOpen) -> bool:
    """Stage 2 on the last bar. It is decided on the week's close only; with the rule
    switched off, every qualified session passes."""
    if not rules.enabled(K + "momentum"):
        return True
    i = len(bars) - 1
    return is_week_close(bars[i].session_date, is_open) and ladder(bars, i, rules).passed


@dataclass
class WatchState:
    """Carried from session to session. momentum_at is the index of the momentum pass that
    keeps the stock on the watch list; blocked_through ends a pass's use after a buy."""

    momentum_at: int | None = None
    watching: bool = False
    blocked_through: int = -1


@dataclass(frozen=True)
class Day:
    index: int
    result: ScreenResult | None  # None: not qualified
    momentum: bool
    watching: bool
    joined: bool  # watching now and not on the previous session
    qualifying: date | None = None  # the week close whose momentum pass keeps it watched


def step(
    ticker: str, bars: Sequence[DayBar], i: int, rules: RuleSet, state: WatchState,
    is_open: IsOpen,
) -> Day:  # fmt: skip
    """Stages 1 to 3 on session i. A pass on the week's close (the qualifying date) keeps the
    stock watched for watch_sessions, even on sessions when it no longer qualifies (owners
    2026-10-20: a drop below the pullback zone does not end the watch). Updates state; buys
    are decided by the caller."""
    upto = bars[: i + 1]
    result = screen(ticker, upto, rules)
    watch = rules.params(K + "watch")
    if (
        result is not None
        and watch["require_trend_confirmed"]
        and result.status != ("trend_confirmed")
    ):
        result = None
    was = state.watching
    mom = result is not None and passes_momentum(upto, rules, is_open)
    if mom and i > state.blocked_through:
        state.momentum_at = i
    sessions = int(watch["watch_sessions"]) if rules.enabled(K + "watch") else 1
    state.watching = state.momentum_at is not None and i - state.momentum_at < sessions
    if not state.watching:
        state.momentum_at = None
    since = bars[state.momentum_at].session_date if state.momentum_at is not None else None
    return Day(i, result, mom, state.watching, state.watching and not was, since)


def buy_votes(
    bars: Sequence[DayBar], fired: dict[str, Fired], i: int, rules: RuleSet
) -> list[Vote]:
    return votes(bars, fired, i, "buy", window_of(K + "buy_vote", rules), rules)


def is_buy(bars: Sequence[DayBar], fired: dict[str, Fired], day: Day, rules: RuleSet) -> bool:
    """Stage 4: a watched stock that qualifies on the session (so its close is inside the
    zone), with enough buy votes in the window."""
    if not day.watching or day.result is None or not in_zone(bars[: day.index + 1], rules):
        return False
    return vote_passes(buy_votes(bars, fired, day.index, rules), K + "buy_vote", rules)


# Holding a position: projection, stops, sell vote (stages 5 and 6)

Exit = Literal["stopped", "trailing_stopped", "sold"]


@dataclass(frozen=True)
class Event:
    # trailing_started, projection_reached, horizon_passed, stopped, trailing_stopped, sold
    kind: str
    index: int
    price: Decimal
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Plan:
    entry: Decimal
    stop_initial: Decimal | None
    projection: Decimal
    projection_pct: Decimal
    horizon_sessions: int
    daily_target: Decimal
    weekly_target: Decimal


def plan(entry: Decimal, rules: RuleSet, projection_pct: Decimal | None = None,
         horizon_sessions: int | None = None) -> Plan:  # fmt: skip
    """The projection and the first stop for a buy (or a holding's own projection)."""
    m = rules.params(K + "momentum")
    pct = projection_pct if projection_pct is not None else Decimal(str(m["projection_pct"]))
    horizon = horizon_sessions if horizon_sessions is not None else int(m["horizon_sessions"])
    projection = entry * (1 + pct / 100)
    daily = (projection - entry) / horizon
    stop = None
    if rules.enabled(K + "stop_loss"):
        stop = entry * (1 - Decimal(str(rules.params(K + "stop_loss")["stop_pct"])) / 100)
    return Plan(entry, stop, projection, pct, horizon, daily, daily * 5)


@dataclass(frozen=True)
class Track:
    """Where a position stands after the last session given."""

    highest_close: Decimal
    trailing_active: bool
    stop_now: Decimal | None
    projection_index: int | None
    events: list[Event]
    exit: Event | None
    exit_votes: list[Vote]
    last_index: int


def track(
    bars: Sequence[DayBar],
    fired: dict[str, Fired],
    entry_index: int,
    p: Plan,
    rules: RuleSet,
    end: int | None = None,
) -> Track:
    """Follows a position from the session after entry_index to end (default: the last bar),
    on closes only. Each session: the stop set by the previous close is checked first, then
    the highest close, the trailing stop, the projection, and the sell vote (spec 08)."""
    last = len(bars) - 1 if end is None else end
    trail = rules.params(K + "trailing_stop")
    trail_on = rules.enabled(K + "trailing_stop")
    trail_after = Decimal(str(trail["trail_after_pct"])) / 100
    trail_pct = Decimal(str(trail["trail_pct"])) / 100
    highest = p.entry
    trailing = False
    stop = p.stop_initial
    projection_at: int | None = None
    events: list[Event] = []
    exit_event: Event | None = None
    exit_votes: list[Vote] = []
    window = window_of(K + "sell_vote", rules)
    for t in range(entry_index + 1, last + 1):
        close = bars[t].c
        if stop is not None and close <= stop:
            kind = "trailing_stopped" if trailing else "stopped"
            exit_event = Event(kind, t, close, {"stop": str(stop)})
            events.append(exit_event)
            last = t
            break
        highest = max(highest, close)
        if trail_on and not trailing and highest >= p.entry * (1 + trail_after):
            trailing = True
            events.append(Event("trailing_started", t, close, {"highest_close": str(highest)}))
        if trailing:
            stop = highest * (1 - trail_pct)
        if projection_at is None and close >= p.projection:
            projection_at = t
            events.append(Event("projection_reached", t, close))
        if t - entry_index == p.horizon_sessions and projection_at is None:
            events.append(Event("horizon_passed", t, close))
        found = votes(bars, fired, t, "sell", window, rules, after=entry_index)
        if vote_passes(found, K + "sell_vote", rules):
            exit_votes = found
            exit_event = Event("sold", t, close, {"votes": [v.key for v in found]})
            events.append(exit_event)
            last = t
            break
    return Track(highest, trailing, stop, projection_at, events, exit_event, exit_votes, last)


def result_pct(entry: Decimal, price: Decimal) -> Decimal:
    return (price - entry) / entry


# Evidence stored with each buy and screen result (CLAUDE.md rule 3)


def _num(v: float) -> float | None:
    return None if np.isnan(v) else round(float(v), 6)


def evidence(
    bars: Sequence[DayBar], fired: dict[str, Fired], i: int, side: Side, window: int,
    rules: RuleSet, after: int = -1,
) -> dict[str, Any]:  # fmt: skip
    """Each indicator's result for the window ending at session i: whether it fired, on which
    session, and its values on session i."""
    found = {v.key: v for v in votes(bars, fired, i, side, window, rules, after)}
    out: dict[str, Any] = {}
    for key in INDICATORS:
        f = fired.get(key)
        entry: dict[str, Any] = {"enabled": f is not None, "fired": key in found}
        if key in found:
            entry["session"] = bars[found[key].index].session_date.isoformat()
            if found[key].names:
                entry["patterns"] = list(found[key].names)
        if f is not None:
            entry["values"] = {name: _num(arr[i]) for name, arr in f.values.items()}
        entry["provisional"] = rules.has(key) and rules.provisional(key)
        out[key] = entry
    return out


def today_values(
    bars: Sequence[DayBar], fired: dict[str, Fired], rules: RuleSet, is_open: IsOpen
) -> dict[str, Any]:
    """The last session's buy and sell evidence, stored on the screen result."""
    i = len(bars) - 1
    return {
        "buy": evidence(bars, fired, i, "buy", window_of(K + "buy_vote", rules), rules),
        "sell": evidence(bars, fired, i, "sell", window_of(K + "sell_vote", rules), rules),
        "momentum": momentum_evidence(bars, rules, is_open),
    }


def momentum_evidence(bars: Sequence[DayBar], rules: RuleSet, is_open: IsOpen) -> dict[str, Any]:
    """The ladder from the latest week close on or before the last bar, as the portal shows
    it: each week back, its rate, and whether enough weeks reached the threshold."""
    i = len(bars) - 1
    while i > 0 and not is_week_close(bars[i].session_date, is_open):
        i -= 1
    lad = ladder(bars, i, rules)
    return {
        "enabled": rules.enabled(K + "momentum"),
        "week_close": lad.session.isoformat(),
        "today": i == len(bars) - 1,
        "close": float(lad.close),
        "threshold": float(lad.threshold),
        "needed": lad.needed,
        "passes": lad.passes,
        "passed": lad.passed,
        "weeks": [
            {
                "weeks": r.weeks,
                "days": r.days,
                "session": r.session.isoformat() if r.session else None,
                "close": None if r.close is None else float(r.close),
                "rate": None if r.rate is None else round(float(r.rate), 6),
                "passed": r.passed,
            }
            for r in lad.rungs
        ],
    }


def has_provisional(found: Sequence[Vote], rules: RuleSet) -> bool:
    return any(rules.provisional(v.key) for v in found)


def session_index(bars: Sequence[DayBar], session: date) -> int | None:
    for k in range(len(bars) - 1, -1, -1):
        if bars[k].session_date == session:
            return k
        if bars[k].session_date < session:
            return None
    return None


def last_index_on_or_before(bars: Sequence[DayBar], session: date) -> int:
    """The index of the last bar on or before session; -1 if every bar is later."""
    for k in range(len(bars) - 1, -1, -1):
        if bars[k].session_date <= session:
            return k
    return -1
