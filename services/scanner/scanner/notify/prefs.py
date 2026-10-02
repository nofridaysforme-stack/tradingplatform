"""Per-owner filtering (spec 11, "Filtering per owner")."""

from datetime import datetime, time
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel

Channel = Literal["webpush", "email", "telegram"]
Kind = Literal["signal", "update", "digest", "holding", "health", "test"]
CHANNELS: tuple[Channel, ...] = ("webpush", "email", "telegram")


class Prefs(BaseModel):
    """notification_prefs, with the table defaults when an owner has no row yet."""

    channels: list[Channel] = ["webpush", "email"]
    strategies: list[str] = ["three_eight", "fib_pivot", "stocks"]
    instrument_ids: list[UUID] | None = None  # None or empty: every enabled pair
    quiet_start: time | None = None
    quiet_end: time | None = None
    include_updates: bool = True


def in_quiet_hours(prefs: Prefs, at: datetime, timezone: str) -> bool:
    """Quiet hours are in the owner's time zone and may cross midnight (22:00 to 07:00)."""
    start, end = prefs.quiet_start, prefs.quiet_end
    if start is None or end is None or start == end:
        return False
    try:
        local = at.astimezone(ZoneInfo(timezone)).time()
    except ZoneInfoNotFoundError:
        local = at.astimezone(ZoneInfo("America/New_York")).time()
    return start <= local < end if start < end else local >= start or local < end


def skip_reason(
    prefs: Prefs,
    *,
    active: bool,
    channel: Channel,
    kind: Kind,
    at: datetime,
    timezone: str,
    strategy: str | None = None,
    instrument_id: UUID | None = None,
) -> str | None:
    """None when the notification should go out on this channel; otherwise why it is skipped.
    Health and test notifications ignore strategy, pair, and quiet-hour settings."""
    if not active:
        return "inactive"
    if channel not in prefs.channels:
        return None if kind == "health" and channel == "email" else "channel_off"
    if kind in ("health", "test"):
        return None
    if kind == "update" and not prefs.include_updates:
        return "updates_off"
    if strategy is not None and strategy not in prefs.strategies:
        return "strategy_off"
    if (
        instrument_id is not None
        and prefs.instrument_ids
        and instrument_id not in prefs.instrument_ids
    ):
        return "pair_off"
    if in_quiet_hours(prefs, at, timezone):
        return "quiet_hours"
    return None
