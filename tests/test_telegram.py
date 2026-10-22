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
from schloss_monitor.school_holidays import SlotAnnotation


def appointment(free_places: int | None, hour: int = 11) -> Appointment:
    return Appointment(
        event_key=f"magische-tiere-2026-11-10-{hour:02d}30",
        start_at=datetime(2026, 11, 10, hour, 30, tzinfo=ZoneInfo("Europe/Berlin")),
        status=AppointmentStatus.AVAILABLE,
        available_places=free_places,
        detail_url="https://example.test/detail",
        booking_url=f"https://example.test/booking/{hour:02d}30",
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


def test_telegram_notifier_batches_alertable_changes_into_one_structured_message() -> None:
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
    annotated = appointment(5)
    notifier.notify(
        [
            Change(ChangeType.NEW, annotated),
            Change(ChangeType.INCREASED, appointment(7, hour=14), previous_available_places=3),
            Change(ChangeType.DECREASED, appointment(2), previous_available_places=7),
            Change(ChangeType.NEW, appointment(None)),
        ],
        {annotated.event_key: SlotAnnotation(True, ("Herbstferien",))},
    )

    assert [url for url, _ in sent] == ["https://api.telegram.org/bottest-token/sendMessage"]
    message = parse_qs(sent[0][1].decode())["text"][0]
    assert "Neue freie Plätze" in message
    assert "[NEU] Dienstag, 10.11.2026, 11:30 – 5 freie Plätze" in message
    assert "[WOCHENENDE | SCHULFERIEN: Herbstferien]" in message
    assert "[MEHR] Dienstag, 10.11.2026, 14:30 – 7 freie Plätze" in message
    assert "https://example.test/booking/1130" in message
    assert "https://example.test/booking/1430" in message


def test_disabled_telegram_notifier_does_not_send() -> None:
    def post_transport(url: str, body: bytes) -> bytes:
        raise AssertionError(f"unexpected request: {url} {body!r}")

    TelegramNotifier(
        enabled=False,
        bot_token="test-token",
        chat_id="123456",
        post_transport=post_transport,
    ).notify([Change(ChangeType.NEW, appointment(5))])

