from typing import Any

import httpx
import pytest
from pywebpush import WebPushException  # type: ignore[import-untyped]

from scanner.config import Settings
from scanner.notify import channels
from scanner.notify.channels import (
    DeliveryError,
    PushSubscription,
    Target,
    TelegramSender,
    WebPushSender,
    build_senders,
)
from scanner.notify.messages import Message

MSG = Message("Long EUR/USD (3/8 Formula)", "Entry 1.08430", "https://desk.example.com/signals/x")
TOKEN = "123456:SECRET-TOKEN"


def telegram(handler: Any) -> TelegramSender:
    return TelegramSender(TOKEN, httpx.Client(transport=httpx.MockTransport(handler)))


def test_telegram_sends_plain_text() -> None:
    seen: list[httpx.Request] = []

    def ok(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"ok": True})

    telegram(ok).send(Target(chat_id=42), MSG)
    body = seen[0].read().decode()
    assert '"chat_id":42' in body and "Entry 1.08430" in body


def test_telegram_errors_never_carry_the_token() -> None:
    def blocked(req: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    with pytest.raises(DeliveryError) as exc:
        telegram(blocked).send(Target(chat_id=42), MSG)
    assert exc.value.permanent and str(exc.value) == "telegram returned 403"

    def down(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=req)

    with pytest.raises(DeliveryError) as exc:
        telegram(down).send(Target(chat_id=42), MSG)
    assert TOKEN not in str(exc.value) and not exc.value.permanent
    assert telegram(down).ready(Target()) == "telegram_not_linked"


def test_push_410_marks_the_subscription_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_webpush(subscription_info: dict[str, Any], **_: Any) -> None:
        if subscription_info["endpoint"] == "https://push/old":
            raise WebPushException("gone", response=httpx.Response(410))

    monkeypatch.setattr(channels, "webpush", fake_webpush)
    sender = WebPushSender("key", "mailto:ops@example.com")
    subs = (
        PushSubscription("https://push/old", "p", "a"),
        PushSubscription("https://push/new", "p", "a"),
    )
    assert sender.send(Target(subscriptions=subs), MSG).gone == ["https://push/old"]
    with pytest.raises(DeliveryError) as exc:
        sender.send(Target(subscriptions=subs[:1]), MSG)
    assert exc.value.permanent and exc.value.gone == ["https://push/old"]
    assert sender.ready(Target()) == "no_subscription"


def test_channels_turn_on_with_their_settings() -> None:
    base = {"database_url": "postgresql://x"}
    assert build_senders(Settings(**base)) == {}  # type: ignore[arg-type]
    full = Settings(
        **base,  # type: ignore[arg-type]
        vapid_private_key="k", vapid_subject="mailto:a@example.com",
        resend_api_key="re_x", email_from="Alerts <a@example.com>", telegram_bot_token=TOKEN,
    )  # fmt: skip
    assert sorted(build_senders(full)) == ["email", "telegram", "webpush"]
    assert TOKEN not in repr(full)
