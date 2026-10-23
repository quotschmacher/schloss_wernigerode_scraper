from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from schloss_monitor.config import load_settings
from schloss_monitor.models import Appointment, AppointmentStatus, CountSource
from schloss_monitor.monitor import (
    PlaywrightScanner,
    ScanResult,
    retry_async,
    run_forever,
    run_once,
    wait_for_page_ready,
)
from schloss_monitor.notifiers.console import ConsoleNotifier
from schloss_monitor.notifiers.telegram import TelegramApiError
from schloss_monitor.storage import MonitorStorage


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

