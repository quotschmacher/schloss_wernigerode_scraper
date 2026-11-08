from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from schloss_monitor.config import load_settings
from schloss_monitor.models import Appointment, AppointmentStatus, Availability, CountSource
from schloss_monitor.monitor import (
    PlaywrightScanner,
    ScanResult,
    poll_telegram_commands,
    retry_async,
    run_forever,
    run_once,
    wait_for_next_scan,
    wait_for_page_ready,
)
from schloss_monitor.notifiers.console import ConsoleNotifier
from schloss_monitor.notifiers.telegram import TelegramApiError
from schloss_monitor.storage import MonitorStorage
from schloss_monitor.telegram_commands import TelegramCommand, TelegramCommandKind


@pytest.mark.asyncio
async def test_poll_telegram_commands_persists_offset_sends_help_and_returns_scan_requests(tmp_path: Path) -> None:
    storage = MonitorStorage(tmp_path / "db.sqlite3")

    class CommandClient:
        def __init__(self) -> None:
            self.help_chat_ids: list[str] = []
            self.list_counts: list[int] = []

        def fetch_updates(self, offset: int | None):
            assert offset is None
            return [{"update_id": 12}, {"update_id": 13}, {"update_id": 14}]

        def parse_updates(self, updates):
            assert updates == [{"update_id": 12}, {"update_id": 13}, {"update_id": 14}]
            return [
                TelegramCommand(TelegramCommandKind.HELP, "123456", 12),
                TelegramCommand(TelegramCommandKind.SCAN, "123456", 13),
                TelegramCommand(TelegramCommandKind.LIST, "123456", 14),
            ]

        def send_help(self, chat_id: str) -> None:
            self.help_chat_ids.append(chat_id)

        def send_list(self, chat_id: str, appointments, annotations) -> None:
            assert chat_id == "123456"
            assert annotations == {}
            self.list_counts.append(len(appointments))

    client = CommandClient()

    assert await poll_telegram_commands(storage, client) == ["123456"]
    assert storage.telegram_update_offset() == 15
    assert client.help_chat_ids == ["123456"]
    assert client.list_counts == [0]
    storage.close()


@pytest.mark.asyncio
async def test_poll_telegram_commands_rejects_scan_requested_during_completed_scan(tmp_path: Path) -> None:
    storage = MonitorStorage(tmp_path / "db.sqlite3")

    class CommandClient:
        def __init__(self) -> None:
            self.rejected_chat_ids: list[str] = []

        def fetch_updates(self, offset: int | None):
            assert offset is None
            return [{"update_id": 17}]

        def parse_updates(self, updates):
            assert updates == [{"update_id": 17}]
            return [TelegramCommand(TelegramCommandKind.SCAN, "123456", 17, received_at=20)]

        def send_help(self, chat_id: str) -> None:
            raise AssertionError(f"unexpected help response for {chat_id}")

        def send_list(self, chat_id: str, appointments) -> None:
            raise AssertionError(f"unexpected list response for {chat_id}")

        def send_scan_already_running(self, chat_id: str) -> None:
            self.rejected_chat_ids.append(chat_id)

    client = CommandClient()

    assert await poll_telegram_commands(storage, client, completed_scan_window=(10, 30)) == []
    assert client.rejected_chat_ids == ["123456"]
    storage.close()


@pytest.mark.asyncio
async def test_wait_for_next_scan_returns_telegram_scan_request_without_waiting_interval(tmp_path: Path) -> None:
    storage = MonitorStorage(tmp_path / "db.sqlite3")
    stop_event = asyncio.Event()

    class CommandClient:
        def fetch_updates(self, offset: int | None):
            assert offset is None
            return [{"update_id": 5}]

        def parse_updates(self, updates):
            assert updates == [{"update_id": 5}]
            return [TelegramCommand(TelegramCommandKind.SCAN, "123456", 5)]

        def send_help(self, chat_id: str) -> None:
            raise AssertionError(f"unexpected help response for {chat_id}")

    assert await wait_for_next_scan(
        interval_seconds=3600,
        command_poll_seconds=5,
        stop_event=stop_event,
        storage=storage,
        command_client=CommandClient(),
    ) == ["123456"]
    storage.close()


@pytest.mark.asyncio
async def test_run_forever_acknowledges_manual_scan_completion(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(Path("config.toml").read_text(encoding="utf-8"), encoding="utf-8")
    settings = load_settings(config)
    storage = MonitorStorage(tmp_path / "db.sqlite3")
    stop_event = asyncio.Event()
    item = Appointment(
        event_key="magische-tiere-2026-11-10-1130",
        start_at=datetime(2026, 11, 10, 11, 30, tzinfo=ZoneInfo("Europe/Berlin")),
        status=AppointmentStatus.AVAILABLE,
        available_places=5,
        detail_url="https://example.test/detail",
        booking_url="https://example.test/booking",
        observed_at=datetime.now(ZoneInfo("UTC")),
        count_source=CountSource.TICKETFRITZ_EXACT,
    )

    class CommandClient:
        def __init__(self) -> None:
            self.fetches = 0
            self.results: list[tuple[str, int]] = []

        def fetch_updates(self, offset: int | None):
            self.fetches += 1
            assert offset is None
            return [{"update_id": 1}]

        def parse_updates(self, updates):
            assert updates == [{"update_id": 1}]
            return [TelegramCommand(TelegramCommandKind.SCAN, "123456", 1)]

        def send_help(self, chat_id: str) -> None:
            raise AssertionError(f"unexpected help response for {chat_id}")

        def send_scan_result(self, chat_id: str, *, changes: int) -> None:
            self.results.append((chat_id, changes))
            stop_event.set()

        def send_scan_failure(self, chat_id: str, error: str) -> None:
            raise AssertionError(f"unexpected scan failure {chat_id}: {error}")

    client = CommandClient()
    await run_forever(settings, storage, StaticScanner(item), NoopNotifier(), stop_event, client)

    assert client.results == [("123456", 0)]
    storage.close()


@pytest.mark.asyncio
async def test_run_forever_reports_scan_errors_to_notifier(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(Path("config.toml").read_text(encoding="utf-8"), encoding="utf-8")
    settings = load_settings(config)
    storage = MonitorStorage(tmp_path / "db.sqlite3")
    stop_event = asyncio.Event()

    class FailingScanner:
        async def scan(self):
            raise RuntimeError("Ticketfritz timeout")

    class ErrorNotifier:
        def report_scan_error(self, error: str) -> None:
            assert error == "Ticketfritz timeout"
            stop_event.set()

    await asyncio.wait_for(
        run_forever(settings, storage, FailingScanner(), ErrorNotifier(), stop_event),
        timeout=0.2,
    )

    storage.close()


@pytest.mark.asyncio
async def test_monitor_loop_exits_when_stop_event_is_set(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(Path("config.toml").read_text(encoding="utf-8"), encoding="utf-8")
    settings = load_settings(config)
    storage = MonitorStorage(tmp_path / "db.sqlite3")
    stop_event = asyncio.Event()
    stop_event.set()

    await run_forever(settings, storage, PlaywrightScanner(settings), ConsoleNotifier(), stop_event)
    storage.close()


@pytest.mark.asyncio
async def test_retry_async_retries_a_transient_browser_error() -> None:
    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("transient timeout")
        return "ok"

    assert await retry_async(operation, attempts=2, delay_seconds=0) == "ok"
    assert attempts == 2


class CookieButton:
    async def count(self) -> int:
        return 1

    async def is_visible(self) -> bool:
        return True

    async def click(self, *, no_wait_after: bool) -> None:
        assert no_wait_after is True


class CookiePage:
    def get_by_role(self, role: str, name: str) -> CookieButton:
        assert (role, name) == ("button", "Nur Auswahl bestätigen")
        return CookieButton()


@pytest.mark.asyncio
async def test_cookie_confirmation_does_not_wait_for_optional_navigation() -> None:
    await PlaywrightScanner._confirm_necessary_cookies(CookiePage())


class ReadyPage:
    async def wait_for_load_state(self, state: str, *, timeout: int) -> None:
        assert state == "domcontentloaded"
        assert timeout == 123


@pytest.mark.asyncio
async def test_booking_availability_uses_public_api_without_booking_page_navigation(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(Path("config.toml").read_text(encoding="utf-8"), encoding="utf-8")
    settings = load_settings(config)
    start_at = datetime(2026, 11, 10, 11, 30, tzinfo=ZoneInfo("Europe/Berlin"))

    class Response:
        status = 200

        async def text(self) -> str:
            return json.dumps(
                {
                    "data": [
                        {
                            "ZeitpunktBezeichnung": "10.11.2026 - 11:30",
                            "AnzahlFrei": 7,
                        }
                    ]
                }
            )

    class Request:
        def __init__(self) -> None:
            self.urls: list[str] = []

        async def get(self, url: str) -> Response:
            self.urls.append(url)
            return Response()

    class Context:
        def __init__(self) -> None:
            self.request = Request()

    class RequestOnlyPage:
        def __init__(self) -> None:
            self.context = Context()

    page = RequestOnlyPage()
    availability = await PlaywrightScanner(settings)._booking_availability(
        page,
        "https://schloss-wernigerode.ticketfritz.de/Event/Kalender/31935/59065?typ=Vorlage",
        start_at,
    )

    assert availability.available_places == 7
    assert page.context.request.urls == [
        "https://schloss-wernigerode.ticketfritz.de/Event/getEvents?"
        "ZeitpunktVon=2026-11-10&ZeitpunktBis=2026-11-10&Typ=Vorlage&Wert=&VorlageOid=31935"
    ]


def test_unverified_ticketfritz_response_keeps_detail_page_slot_as_available_unknown() -> None:
    availability = PlaywrightScanner._availability_for_detail_slot(
        Availability(AppointmentStatus.UNKNOWN, None, CountSource.UNKNOWN),
        datetime(2026, 12, 18, 13, 30, tzinfo=ZoneInfo("Europe/Berlin")),
    )

    assert availability.status is AppointmentStatus.AVAILABLE
    assert availability.available_places is None
    assert availability.source is CountSource.UNKNOWN


@pytest.mark.asyncio
async def test_wait_for_page_ready_waits_for_dom_content_loaded() -> None:
    await wait_for_page_ready(ReadyPage(), timeout_ms=123)


class FailingNotifier:
    def report_slots(self, appointments, annotations=None) -> None:
        del appointments, annotations

    def notify(self, changes, annotations=None) -> None:
        del changes, annotations
        raise TelegramApiError("chat not accessible")


class StaticScanner:
    def __init__(self, appointment: Appointment) -> None:
        self.appointment = appointment

    async def scan(self) -> ScanResult:
        return ScanResult([self.appointment], set(), 1)


class StaticResultScanner:
    def __init__(self, result: ScanResult) -> None:
        self.result = result

    async def scan(self) -> ScanResult:
        return self.result


class NoopNotifier:
    def report_slots(self, appointments, annotations=None) -> None:
        del appointments, annotations

    def notify(self, changes, annotations=None) -> None:
        del changes, annotations


@pytest.mark.asyncio
async def test_scan_summary_separates_available_and_sold_out_slots(tmp_path: Path, caplog) -> None:
    caplog.set_level("INFO")
    config = tmp_path / "config.toml"
    config.write_text(Path("config.toml").read_text(encoding="utf-8"), encoding="utf-8")
    settings = load_settings(config)
    observed_at = datetime.now(ZoneInfo("UTC"))
    available = Appointment(
        event_key="magische-tiere-2026-11-10-1130",
        start_at=datetime(2026, 11, 10, 11, 30, tzinfo=ZoneInfo("Europe/Berlin")),
        status=AppointmentStatus.AVAILABLE,
        available_places=5,
        detail_url="https://example.test/detail",
        booking_url="https://example.test/booking",
        observed_at=observed_at,
        count_source=CountSource.TICKETFRITZ_EXACT,
    )
    sold_out = Appointment(
        event_key="magische-tiere-2026-11-10-1330",
        start_at=datetime(2026, 11, 10, 13, 30, tzinfo=ZoneInfo("Europe/Berlin")),
        status=AppointmentStatus.SOLD_OUT,
        available_places=0,
        detail_url="https://example.test/detail",
        booking_url="https://example.test/booking",
        observed_at=observed_at,
        count_source=CountSource.TICKETFRITZ_SOLD_OUT,
    )
    storage = MonitorStorage(tmp_path / "db.sqlite3")

    await run_once(settings, storage, StaticResultScanner(ScanResult([available, sold_out], set(), 1)), NoopNotifier())

    assert "scan finished days=1 slots=2 available=1 sold_out=1 changes=1" in caplog.text
    storage.close()


@pytest.mark.asyncio
async def test_notification_failure_does_not_commit_new_snapshot(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(Path("config.toml").read_text(encoding="utf-8"), encoding="utf-8")
    settings = load_settings(config)
    storage = MonitorStorage(tmp_path / "db.sqlite3")
    appointment = Appointment(
        event_key="magische-tiere-2026-11-10-1130",
        start_at=datetime(2026, 11, 10, 11, 30, tzinfo=ZoneInfo("Europe/Berlin")),
        status=AppointmentStatus.AVAILABLE,
        available_places=5,
        detail_url="https://example.test/detail",
        booking_url="https://example.test/booking",
        observed_at=datetime.now(ZoneInfo("UTC")),
        count_source=CountSource.TICKETFRITZ_EXACT,
    )

    with pytest.raises(TelegramApiError, match="chat not accessible"):
        await run_once(settings, storage, StaticScanner(appointment), FailingNotifier())

    assert storage.current_appointments() == {}
    storage.close()

