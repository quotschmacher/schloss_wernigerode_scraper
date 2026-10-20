from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from schloss_monitor.config import load_settings
from schloss_monitor.monitor import (
    PlaywrightScanner,
    retry_async,
    run_forever,
    wait_for_page_ready,
)
from schloss_monitor.notifiers.console import ConsoleNotifier
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
