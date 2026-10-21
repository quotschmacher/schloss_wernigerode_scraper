from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

import pytest

from schloss_monitor.models import Appointment, AppointmentStatus, Change, ChangeType, CountSource
from schloss_monitor.notifiers.telegram import (
    TelegramApiError,
    TelegramNotifier,
    verify_bot_token,
    verify_chat_access,
)


def appointment(free_places: int | None) -> Appointment:
    return Appointment(
        event_key="magische-tiere-2026-11-10-1130",
        start_at=datetime(2026, 11, 10, 11, 30, tzinfo=ZoneInfo("Europe/Berlin")),
        status=AppointmentStatus.AVAILABLE,
        available_places=free_places,
        detail_url="https://example.test/detail",
        booking_url="https://example.test/booking",
        observed_at=datetime.now(ZoneInfo("UTC")),
        count_source=CountSource.TICKETFRITZ_EXACT,
    )


def test_get_me_validates_bot_token_without_sending_message() -> None:
    requested: list[str] = []

    def transport(url: str) -> bytes:
        requested.append(url)
        return json.dumps({"ok": True, "result": {"username": "slot_monitor_bot"}}).encode()

    assert verify_bot_token("test-token", transport=transport) == "slot_monitor_bot"
    assert requested == ["https://api.telegram.org/bottest-token/getMe"]


def test_get_me_rejects_an_invalid_token() -> None:
    def transport(url: str) -> bytes:
        del url
        return b'{"ok":false,"description":"Unauthorized"}'

    with pytest.raises(TelegramApiError, match="Unauthorized"):
        verify_bot_token("bad-token", transport=transport)


def test_get_chat_validates_configured_recipient_without_sending_message() -> None:
    requested: list[str] = []

    def transport(url: str) -> bytes:
        requested.append(url)
        return b'{"ok":true,"result":{"id":123456,"type":"private"}}'

    verify_chat_access("test-token", "123456", transport=transport)
    assert requested == ["https://api.telegram.org/bottest-token/getChat?chat_id=123456"]


def test_telegram_notifier_sends_only_new_or_increased_known_availability() -> None:
    sent: list[tuple[str, bytes]] = []

    def post_transport(url: str, body: bytes) -> bytes:
        sent.append((url, body))
        return b'{"ok":true,"result":{"message_id":1}}'

    notifier = TelegramNotifier(
        enabled=True,
        bot_token="test-token",
        chat_id="123456",
        post_transport=post_transport,
    )
    notifier.notify(
        [
            Change(ChangeType.NEW, appointment(5)),
            Change(ChangeType.INCREASED, appointment(7), previous_available_places=3),
            Change(ChangeType.DECREASED, appointment(2), previous_available_places=7),
            Change(ChangeType.NEW, appointment(None)),
        ]
    )

    assert [url for url, _ in sent] == [
        "https://api.telegram.org/bottest-token/sendMessage",
        "https://api.telegram.org/bottest-token/sendMessage",
    ]
    first_message = parse_qs(sent[0][1].decode())["text"][0]
    assert "Dienstag, 10.11.2026, 11:30" in first_message
    assert "5 freie Plätze" in first_message
    assert "https://example.test/booking" in first_message


def test_disabled_telegram_notifier_does_not_send() -> None:
    def post_transport(url: str, body: bytes) -> bytes:
        raise AssertionError(f"unexpected request: {url} {body!r}")

    TelegramNotifier(
        enabled=False,
        bot_token="test-token",
        chat_id="123456",
        post_transport=post_transport,
    ).notify([Change(ChangeType.NEW, appointment(5))])

