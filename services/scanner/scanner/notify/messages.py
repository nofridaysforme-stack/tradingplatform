"""Message templates (spec 11). Plain text with one structure for every channel; email adds a
simple HTML layout in the portal's colours. No em dashes."""

import html
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from scanner.time import to_new_york

Direction = Literal["long", "short"]

STRATEGY_NAMES = {"three_eight": "3/8 Formula", "fib_pivot": "Fib Pivot"}
FIB_LEVELS = {
    "break": "break",
    "confirmation": "confirmation",
    "take_profit": "take profit",
    "reset": "reset",
    "pivot": "pivot",
    "opposite_break": "opposite break",
}


@dataclass(frozen=True)
class Message:
    title: str
    body: str
    url: str | None = None

    def text(self) -> str:
        """Telegram and the email plain-text part."""
        parts = [self.title, "", self.body]
        if self.url:
            parts += ["", self.url]
        return "\n".join(parts)

    def html(self) -> str:
        """Email HTML: ink on ledger, ruled, no images (spec 13 tokens)."""
        lines = "".join(
            f"<p style='margin:0 0 8px'>{html.escape(line)}</p>"
            for line in self.body.split("\n")
            if line
        )
        link = (
            f"<p style='margin:16px 0 0'><a href='{html.escape(self.url)}' "
            "style='color:#2563C9'>Open in the portal</a></p>"
            if self.url
            else ""
        )
        return (
            "<!doctype html><html><body style='margin:0;padding:24px;background:#F6F7F5;"
            "color:#23282E;font:15px/1.5 IBM Plex Sans,Helvetica,Arial,sans-serif'>"
            "<div style='max-width:560px;border-top:1px solid #C9CED3;padding-top:16px'>"
            f"<h1 style='font-size:18px;margin:0 0 12px'>{html.escape(self.title)}</h1>"
            f"{lines}{link}<p style='margin:24px 0 0;color:#5A626B;font-size:13px'>"
            "Trading desk suggests trades from your own rules. It does not place trades. "
            "Every decision is yours.</p></div></body></html>"
        )


def ny_clock(at: datetime) -> str:
    return to_new_york(at).strftime("%H:%M")


def fmt(price: float, decimals: int) -> str:
    return f"{price:.{decimals}f}"


@dataclass(frozen=True)
class SignalFacts:
    id: str
    strategy: str
    symbol: str
    direction: Direction
    decimals: int
    entry: float
    stop: float
    target: float
    reward_risk: float
    indicators: list[str]  # names of fired indicators, ring order
    has_provisional: bool
    broker: str | None  # prices already adjusted for this broker when set
    stop_at: str | None = None  # Fib Pivot
    target_at: str | None = None


def signal_message(s: SignalFacts, base_url: str) -> Message:
    d = s.decimals
    title = f"{s.direction.capitalize()} {s.symbol} ({STRATEGY_NAMES.get(s.strategy, s.strategy)})"
    if s.strategy == "fib_pivot":
        stop = f" ({FIB_LEVELS.get(s.stop_at or '', s.stop_at)})" if s.stop_at else ""
        target = f" ({FIB_LEVELS.get(s.target_at or '', s.target_at)})" if s.target_at else ""
        lines = [
            f"Break {fmt(s.entry, d)} crossed. Stop {fmt(s.stop, d)}{stop}. "
            f"Target {fmt(s.target, d)}{target}."
        ]
        lines.append(f"Reward to risk {s.reward_risk:.1f}.")
    else:
        lines = [f"Entry {fmt(s.entry, d)}  Stop {fmt(s.stop, d)}  Target {fmt(s.target, d)}"]
        why = f" {', '.join(s.indicators)}." if s.indicators else ""
        lines.append(f"Reward to risk {s.reward_risk:.1f}.{why}")
    if s.has_provisional:
        lines.append("Includes a provisional rule.")
    lines.append(f"Prices adjusted for {s.broker}." if s.broker else "Reference prices.")
    return Message(title, "\n".join(lines), f"{base_url}/signals/{s.id}")


UPDATE_VERBS = {
    "confirmed": "confirmed",
    "reset_reached": "reached reset",
    "target_hit": "hit target",
    "stop_hit": "hit stop",
    "expired": "expired",
    "ambiguous": "closed (stop and target in one bar)",
    "invalidated": "was marked invalid",
}


def update_message(
    *,
    signal_id: str,
    symbol: str,
    direction: Direction,
    kind: str,
    at: datetime,
    price: float | None,
    decimals: int,
    result_pips: float | None,
    base_url: str,
) -> Message:
    title = f"{symbol} {direction} {UPDATE_VERBS.get(kind, kind.replace('_', ' '))}"
    when = f"{ny_clock(at)} New York"
    if result_pips is not None and kind in ("target_hit", "stop_hit", "expired", "ambiguous"):
        sign = "+" if result_pips > 0 else ""
        body = f"{sign}{result_pips:g} pips. Closed {when}."
    elif price is not None:
        body = f"At {fmt(price, decimals)}, {when}."
    else:
        body = f"{when}."
    return Message(title, body, f"{base_url}/signals/{signal_id}")


@dataclass(frozen=True)
class WatchRow:
    ticker: str
    close: float
    below_high: float  # fraction below the 52-week high
    apr_10: float | None


def pct(v: float | None) -> str:
    return "" if v is None else f"{v * 100:,.0f}%"


def money(v: float) -> str:
    """Two decimals, half up (22.895 shows as 22.90, as the spec examples do)."""
    return str(Decimal(repr(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def pct1(v: float) -> str:
    sign = "+" if v > 0 else ""
    return f"{sign}{v * 100:.1f}%"


def watch_message(rows: list[WatchRow], session: str, base_url: str) -> Message:
    """Spec 11, stock watch list digest."""
    n = len(rows)
    title = f"{n} stock{'' if n == 1 else 's'} joined the watch list today"
    lines = [f"After the {session} session:"]
    lines += [
        f"{r.ticker}  close {money(r.close)}  {r.below_high * 100:.1f}% below the 52-week high  "
        f"APR 10-day {pct(r.apr_10)}"
        for r in rows
    ]
    return Message(title, "\n".join(lines), f"{base_url}/stocks?session={session}&stage=watching")


INDICATOR_NAMES = {
    "stocks.ind_candle": "bullish candle",
    "stocks.ind_macd": "MACD crossed up",
    "stocks.ind_pivot": "pivot hooked up",
    "stocks.ind_rsi": "RSI crossed",
    "stocks.ind_stoch": "Stochastics crossed",
}
SELL_NAMES = {
    "stocks.ind_candle": "bearish candle",
    "stocks.ind_macd": "MACD crossed down",
    "stocks.ind_pivot": "pivot hooked down",
    "stocks.ind_rsi": "RSI crossed",
    "stocks.ind_stoch": "Stochastics crossed",
}


@dataclass(frozen=True)
class StockBuy:
    signal_id: str
    ticker: str
    session: str
    entry: float
    stop: float
    stop_pct: float
    projection: float
    projection_pct: float
    horizon: int
    voted: list[str]  # readable indicator names
    has_provisional: bool


def stock_buy_message(b: StockBuy, base_url: str) -> Message:
    """Spec 11, stock buy."""
    lines = [
        f"{len(b.voted)} of 5 indicators: {', '.join(b.voted)}.",
        f"Stop {money(b.stop)} ({b.stop_pct:g}%). Projection {money(b.projection)} "
        f"({b.projection_pct:g}% in {b.horizon} sessions). Close of {b.session}.",
    ]
    if b.has_provisional:
        lines.append("Includes a provisional rule.")
    title = f"Buy signal: {b.ticker} at {money(b.entry)}"
    return Message(title, "\n".join(lines), f"{base_url}/stocks/{b.ticker}")


EXIT_WORDS = {"stopped": "stop", "trailing_stopped": "trailing stop", "sold": "sell signal"}


def stock_exit_message(
    *, ticker: str, kind: str, price: float, entry: float, sessions: int, highest: float,
    voted: list[str], base_url: str, holding: bool = False,
) -> Message:  # fmt: skip
    """Spec 11, stock sell. For a holding the result is from the owner's purchase price."""
    change = (price - entry) / entry
    whose = "your holding " if holding else ""
    title = f"Sell: {whose}{ticker} {EXIT_WORDS.get(kind, kind)} at {money(price)}"
    body = (
        f"{pct1(change)} from {money(entry)} in {sessions} session{'' if sessions == 1 else 's'}."
    )
    if kind != "stopped":
        body += f" Highest close {money(highest)}."
    if voted:
        body += f" {', '.join(voted)}."
    url = f"{base_url}/holdings" if holding else f"{base_url}/stocks/{ticker}"
    return Message(title, body, url)


def stock_update_message(
    *, ticker: str, kind: str, price: float, entry: float, stop: float | None,
    projection: float, horizon: int, base_url: str, holding: bool = False,
) -> Message:  # fmt: skip
    """Information updates on an open buy or a holding."""
    whose = "Your holding " if holding else ""
    url = f"{base_url}/holdings" if holding else f"{base_url}/stocks/{ticker}"
    if kind == "trailing_started":
        stop_text = f" at {money(stop)}" if stop is not None else ""
        return Message(
            f"{whose}{ticker}: trailing stop started{stop_text}",
            f"Closed {money(price)}, {pct1((price - entry) / entry)} from {money(entry)}.",
            url,
        )
    if kind == "projection_reached":
        return Message(
            f"{whose}{ticker} reached its projection",
            f"Closed {money(price)}, at or above the projected {money(projection)}. "
            "The trade rides until a stop or a sell signal.",
            url,
        )
    return Message(
        f"{whose}{ticker} passed {horizon} sessions without its projection",
        f"Closed {money(price)}; the projection is {money(projection)}.",
        url,
    )


def health_message(condition: str, detail: str, *, resolved: bool, base_url: str) -> Message:
    if resolved:
        return Message(
            f"Resolved: {condition_name(condition)}",
            detail or "Back to normal.",
            f"{base_url}/health",
        )
    return Message(f"Health alert: {condition_name(condition)}", detail, f"{base_url}/health")


def condition_name(condition: str) -> str:
    kind, _, subject = condition.partition(":")
    names = {
        "heartbeat_stale": "scanner heartbeat is late",
        "pair_stale": f"no new bars for {subject}",
        "provider_auth": f"{subject} rejected the API key",
        "job_failing": f"{subject} failed three runs in a row",
    }
    return names.get(kind, condition)


def test_message(channel: str, base_url: str) -> Message:
    return Message(
        "Test notification",
        f"Notifications reach you on {CHANNEL_NAMES.get(channel, channel)}.",
        f"{base_url}/settings",
    )


CHANNEL_NAMES = {"webpush": "this device", "email": "email", "telegram": "Telegram"}
