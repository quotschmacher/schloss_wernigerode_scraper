from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ..models import Appointment, AppointmentStatus, Change, ChangeType
from ..school_holidays import SlotAnnotation

type Transport = Callable[[str], bytes]
type PostTransport = Callable[[str, bytes], bytes]


class TelegramApiError(RuntimeError):
    """The Telegram Bot API rejected or could not validate a token."""


def _default_transport(url: str) -> bytes:
    try:
        with urlopen(url, timeout=10) as response:  # noqa: S310 -- fixed Telegram API origin
            return response.read()
    except OSError as error:
        raise TelegramApiError(f"Telegram getMe request failed: {error}") from error


def _default_post_transport(url: str, body: bytes) -> bytes:
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 -- fixed Telegram API origin
            return response.read()
    except HTTPError as error:
        try:
            _telegram_response(error.read(), "sendMessage")
        except TelegramApiError as api_error:
            raise api_error from error
        raise AssertionError("unreachable") from error
    except OSError as error:
        raise TelegramApiError(f"Telegram sendMessage request failed: {error}") from error


def _telegram_response(payload: bytes, operation: str) -> dict[str, object]:
    try:
        decoded = json.loads(payload)
    except (TypeError, ValueError) as error:
        raise TelegramApiError(f"Telegram {operation} response was invalid: {error}") from error
    if not isinstance(decoded, dict) or decoded.get("ok") is not True:
        description = decoded.get("description", "unknown Telegram API error") if isinstance(decoded, dict) else "invalid response"
        raise TelegramApiError(str(description))
    return decoded


def verify_bot_token(bot_token: str, *, transport: Transport = _default_transport) -> str:
    """Call only Telegram's read-only getMe endpoint; never send a message."""
    url = f"https://api.telegram.org/bot{quote(bot_token, safe='')}/getMe"
    payload = _telegram_response(transport(url), "getMe")
    result = payload.get("result")
    username = result.get("username") if isinstance(result, dict) else None
    if not isinstance(username, str) or not username:
        raise TelegramApiError("Telegram getMe response did not contain a bot username")
    return username


def verify_chat_access(bot_token: str, chat_id: str, *, transport: Transport = _default_transport) -> None:
    query = urlencode({"chat_id": chat_id})
    url = f"https://api.telegram.org/bot{quote(bot_token, safe='')}/getChat?{query}"
    _telegram_response(transport(url), "getChat")


@dataclass(frozen=True)
class TelegramNotifier:
    """Sends Telegram alerts only for newly available or increased known capacity."""

    enabled: bool = False
    bot_token: str | None = None
    chat_id: str | None = None
    post_transport: PostTransport = _default_post_transport

    def report_slots(
        self, appointments: Sequence[Appointment], annotations: Mapping[str, SlotAnnotation] | None = None
    ) -> None:
        del appointments, annotations
        return None

    def notify(
        self, changes: Sequence[Change], annotations: Mapping[str, SlotAnnotation] | None = None
    ) -> None:
        if not self.enabled:
            return
        if not self.bot_token or not self.chat_id:
            raise TelegramApiError("Telegram notifier requires bot token and chat ID")
        alerts = [
            change
            for change in changes
            if change.kind in {ChangeType.NEW, ChangeType.INCREASED}
            and change.appointment.available_places is not None
            and change.appointment.status is AppointmentStatus.AVAILABLE
        ]
        if alerts:
            self._send_batch(alerts, annotations or {})

    def _send_batch(self, changes: Sequence[Change], annotations: Mapping[str, SlotAnnotation]) -> None:
        assert self.bot_token is not None
        assert self.chat_id is not None
        url = f"https://api.telegram.org/bot{quote(self.bot_token, safe='')}/sendMessage"
        body = urlencode(
            {
                "chat_id": self.chat_id,
                "text": self._message_text(changes, annotations),
                "disable_web_page_preview": "true",
            }
        ).encode()
        _telegram_response(self.post_transport(url, body), "sendMessage")

    @staticmethod
    def _message_text(
        changes: Sequence[Change], annotations: Mapping[str, SlotAnnotation]
    ) -> str:
        weekdays = (
            "Montag",
            "Dienstag",
            "Mittwoch",
            "Donnerstag",
            "Freitag",
            "Samstag",
            "Sonntag",
        )
        lines = ["Neue freie Plätze:", ""]
        for change in sorted(changes, key=lambda item: item.appointment.start_at):
            appointment = change.appointment
            weekday = weekdays[appointment.start_at.weekday()]
            when = appointment.start_at.strftime("%d.%m.%Y, %H:%M")
            label = "NEU" if change.kind is ChangeType.NEW else "MEHR"
            annotation = annotations.get(appointment.event_key)
            markers = f" [{' | '.join(annotation.labels)}]" if annotation and annotation.labels else ""
            lines.extend(
                [
                    f"• [{label}] {weekday}, {when} – {appointment.available_places} freie Plätze{markers}",
                    appointment.booking_url,
                    "",
                ]
            )
        return "\n".join(lines).rstrip()

