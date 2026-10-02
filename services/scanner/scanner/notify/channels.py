"""Delivery channels (spec 11). Each send has a 10-second timeout. Errors never carry secrets:
the Telegram token sits in the request URL, so its errors are rewritten before they are
logged or stored."""

import json
import logging
from dataclasses import dataclass, field
from typing import Protocol

import httpx
import resend
from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]

from scanner.config import Settings
from scanner.notify.messages import Message
from scanner.notify.prefs import Channel

log = logging.getLogger(__name__)

TIMEOUT = 10.0


@dataclass(frozen=True)
class PushSubscription:
    endpoint: str
    p256dh: str
    auth: str


@dataclass(frozen=True)
class Target:
    """Where one owner receives a channel: their push subscriptions, email, or chat id."""

    subscriptions: tuple[PushSubscription, ...] = ()
    email: str | None = None
    chat_id: int | None = None


@dataclass
class SendResult:
    gone: list[str] = field(default_factory=list)  # push endpoints to delete (404 or 410)


class DeliveryError(Exception):
    """A send failed. permanent=True means retrying cannot help."""

    def __init__(
        self, message: str, *, permanent: bool = False, gone: list[str] | None = None
    ) -> None:
        super().__init__(message)
        self.permanent = permanent
        self.gone = gone or []


class Sender(Protocol):
    def ready(self, target: Target) -> str | None:
        """None when this target can receive the channel; otherwise why not."""
        ...

    def send(self, target: Target, message: Message) -> SendResult: ...


class WebPushSender:
    def __init__(self, private_key: str, subject: str) -> None:
        self._key = private_key
        self._claims = {"sub": subject}

    def ready(self, target: Target) -> str | None:
        return None if target.subscriptions else "no_subscription"

    def send(self, target: Target, message: Message) -> SendResult:
        payload = json.dumps({"title": message.title, "body": message.body, "url": message.url})
        gone: list[str] = []
        delivered = 0
        last_error = ""
        for sub in target.subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=self._key,
                    vapid_claims=dict(self._claims),
                    timeout=TIMEOUT,
                )
                delivered += 1
            except WebPushException as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status in (404, 410):
                    gone.append(sub.endpoint)
                last_error = f"push service returned {status}" if status else "push failed"
            except Exception as exc:  # network errors
                last_error = f"push failed: {type(exc).__name__}"
        if delivered == 0:
            raise DeliveryError(
                last_error or "no subscription",
                permanent=len(gone) == len(target.subscriptions),
                gone=gone,
            )
        return SendResult(gone=gone)


class EmailSender:
    def __init__(self, api_key: str, sender: str) -> None:
        self._key = api_key
        self._from = sender

    def ready(self, target: Target) -> str | None:
        return None if target.email else "no_email"

    def send(self, target: Target, message: Message) -> SendResult:
        assert target.email
        resend.api_key = self._key
        try:
            resend.Emails.send(
                {
                    "from": self._from,
                    "to": [target.email],
                    "subject": message.title,
                    "text": message.text(),
                    "html": message.html(),
                }
            )
        except Exception as exc:
            raise DeliveryError(f"email failed: {type(exc).__name__}") from None
        return SendResult()


class TelegramSender:
    def __init__(self, token: str, client: httpx.Client | None = None) -> None:
        self._token = token
        self._client = client or httpx.Client(timeout=TIMEOUT)

    def ready(self, target: Target) -> str | None:
        return None if target.chat_id else "telegram_not_linked"

    def send(self, target: Target, message: Message) -> SendResult:
        try:
            resp = self._client.post(
                f"https://api.telegram.org/bot{self._token}/sendMessage",
                json={
                    "chat_id": target.chat_id,
                    "text": message.text(),
                    "disable_web_page_preview": True,
                },
            )
        except httpx.HTTPError as exc:
            # The URL carries the token, so only the error type is kept.
            raise DeliveryError(f"telegram failed: {type(exc).__name__}") from None
        if resp.status_code != 200:
            # 400 bad chat, 403 the owner blocked the bot: retrying cannot help.
            raise DeliveryError(
                f"telegram returned {resp.status_code}", permanent=resp.status_code in (400, 403)
            )
        return SendResult()


def build_senders(settings: Settings) -> dict[Channel, Sender]:
    """The channels whose keys are set. Missing ones are skipped with a reason."""
    out: dict[Channel, Sender] = {}
    if settings.vapid_private_key and settings.vapid_subject:
        out["webpush"] = WebPushSender(
            settings.vapid_private_key.get_secret_value(), settings.vapid_subject
        )
    if settings.resend_api_key and settings.email_from:
        out["email"] = EmailSender(settings.resend_api_key.get_secret_value(), settings.email_from)
    if settings.telegram_bot_token:
        out["telegram"] = TelegramSender(settings.telegram_bot_token.get_secret_value())
    return out
