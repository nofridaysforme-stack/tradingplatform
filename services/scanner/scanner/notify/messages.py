"""Message templates (spec 11). Plain text with one structure for every channel; email adds a
simple HTML layout in the portal's colours. No em dashes."""

import html
from dataclasses import dataclass
from datetime import datetime
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
class DigestRow:
    ticker: str
    close: float
    apr_20: float | None
    apr_50: float | None


def pct(v: float | None) -> str:
    return "" if v is None else f"{v * 100:,.0f}%"


def digest_message(rows: list[DigestRow], session: str, base_url: str) -> Message:
    n = len(rows)
    title = f"{n} stock{'' if n == 1 else 's'} confirmed {'its' if n == 1 else 'their'} trend today"
    lines = [f"After the {session} session:"]
    lines += [
        f"{r.ticker}  close {r.close:.2f}  APR 20-day {pct(r.apr_20)}  APR 50-day {pct(r.apr_50)}"
        for r in rows
    ]
    return Message(
        title, "\n".join(lines), f"{base_url}/stocks?session={session}&status=trend_confirmed"
    )


def holding_message(
    *, ticker: str, alert: str, target: float, last_close: float, horizon: int, base_url: str
) -> Message:
    if alert == "target_reached":
        return Message(
            f"{ticker} reached its sales target",
            f"Closed {last_close:.2f}, at or above the target {target:.2f}.",
            f"{base_url}/holdings",
        )
    return Message(
        f"{ticker} passed {horizon} sessions without its target",
        f"Closed {last_close:.2f}; the target is {target:.2f}. Review the holding.",
        f"{base_url}/holdings",
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
