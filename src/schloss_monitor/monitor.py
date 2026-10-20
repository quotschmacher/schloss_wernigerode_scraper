from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .booking_scraper import parse_ticketfritz_availability
from .calendar_scraper import CalendarScraper
from .config import Settings
from .detail_scraper import parse_detail_slots
from .models import Appointment, AppointmentStatus
from .notifiers.base import Notifier
from .storage import MonitorStorage

LOG = logging.getLogger(__name__)


async def retry_async[T](
    operation: Callable[[], Awaitable[T]], *, attempts: int, delay_seconds: float
) -> T:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except (TimeoutError, PlaywrightTimeoutError, PlaywrightError):
            if attempt == attempts:
                raise
            LOG.warning("transient browser timeout; retrying attempt=%s/%s", attempt, attempts)
            await asyncio.sleep(delay_seconds)
    raise AssertionError("unreachable")


async def wait_for_page_ready(page: Page, timeout_ms: int) -> None:
    await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)


class ScanError(RuntimeError):
    """A scan was incomplete and must not replace the stored snapshot."""


@dataclass(frozen=True)
class ScanResult:
    appointments: list[Appointment]
    protected_dates: set[str]
    calendar_days: int


class PlaywrightScanner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def scan(self) -> ScanResult:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.settings.scraper.headless)
            context = await browser.new_context()
            calendar_page = await context.new_page()
            detail_page = await context.new_page()
            booking_page = await context.new_page()
            try:
                calendar = CalendarScraper(
                    self.settings.scraper.url,
                    self.settings.scraper.navigation_timeout_ms,
                    self.settings.scraper.max_load_more_clicks,
                )
                entries = await calendar.discover(calendar_page)
                protected_dates = {entry.event_date.isoformat() for entry in entries if entry.overview_sold_out}
                appointments: list[Appointment] = []
                for entry in entries:
                    if entry.overview_sold_out:
                        LOG.info("skipping overview-sold-out date=%s", entry.event_date)
                        continue
                    await detail_page.goto(
                        entry.detail_url,
                        wait_until="domcontentloaded",
                        timeout=self.settings.scraper.navigation_timeout_ms,
                    )
                    for slot in parse_detail_slots(await detail_page.content(), entry.detail_url):
                        availability = await self._booking_availability(booking_page, slot.booking_url, slot.start_at)
                        if availability.status is AppointmentStatus.UNKNOWN:
                            raise ScanError(f"booking response did not verify slot {slot.start_at.isoformat()}")
                        event_key = f"magische-tiere-{slot.start_at:%Y-%m-%d-%H%M}"
                        appointments.append(
                            Appointment(
                                event_key=event_key,
                                start_at=slot.start_at,
                                status=availability.status,
                                available_places=availability.available_places,
                                detail_url=entry.detail_url,
                                booking_url=slot.booking_url,
                                observed_at=datetime.now(UTC),
                                count_source=availability.source,
                            )
                        )
                        await asyncio.sleep(self.settings.scraper.request_delay_seconds)
                return ScanResult(appointments, protected_dates, len(entries))
            finally:
                await context.close()
                await browser.close()

    async def _booking_availability(self, page: Page, booking_url: str, start_at: datetime):
        await retry_async(
            lambda: page.goto(
                booking_url,
                wait_until="domcontentloaded",
                timeout=self.settings.scraper.navigation_timeout_ms,
            ),
            attempts=2,
            delay_seconds=self.settings.scraper.request_delay_seconds,
        )
        await self._confirm_necessary_cookies(page)
        await wait_for_page_ready(page, self.settings.scraper.navigation_timeout_ms)
        template_id = self._template_id(booking_url)
        query = urlencode(
            {
                "ZeitpunktVon": start_at.date().isoformat(),
                "ZeitpunktBis": start_at.date().isoformat(),
                "Typ": "Vorlage",
                "Wert": "",
                "VorlageOid": template_id,
            }
        )
        endpoint = f"/Event/getEvents?{query}"
        async def fetch_availability() -> object:
            await wait_for_page_ready(page, self.settings.scraper.navigation_timeout_ms)
            return await page.evaluate(
                """async endpoint => {
                    const response = await fetch(endpoint, {credentials: 'same-origin'});
                    return {status: response.status, body: await response.text()};
                }""",
                endpoint,
            )

        response = await retry_async(
            fetch_availability,
            attempts=2,
            delay_seconds=self.settings.scraper.request_delay_seconds,
        )
        if not isinstance(response, dict) or response.get("status") != 200:
            raise ScanError(f"Ticketfritz availability request failed for {start_at.isoformat()}")
        body = response.get("body")
        if not isinstance(body, str):
            raise ScanError("Ticketfritz availability response had no text body")
        return parse_ticketfritz_availability(body, start_at)

    @staticmethod
    def _template_id(booking_url: str) -> str:
        parsed = urlparse(booking_url)
        parts = [part for part in parsed.path.split("/") if part]
        try:
            return parts[parts.index("Kalender") + 1]
        except (ValueError, IndexError) as error:
            query = parse_qs(parsed.query)
            fallback = query.get("VorlageOid", [None])[0]
            if not fallback:
                raise ScanError(f"unexpected Ticketfritz booking URL: {booking_url}") from error
            return fallback

    @staticmethod
    async def _confirm_necessary_cookies(page: Page) -> None:
        button = page.get_by_role("button", name="Nur Auswahl bestätigen")
        if await button.count() and await button.is_visible():
            await button.click(no_wait_after=True)


async def run_once(settings: Settings, storage: MonitorStorage, scanner: PlaywrightScanner, notifier: Notifier) -> int:
    try:
        result = await scanner.scan()
    except Exception as error:
        storage.record_failed_scan(str(error))
        raise
    notifier.report_slots(result.appointments)
    changes = storage.commit_successful_scan(result.appointments, result.protected_dates)
    notifier.notify(changes)
    LOG.info(
        "scan finished days=%s slots=%s changes=%s",
        result.calendar_days,
        len(result.appointments),
        len(changes),
    )
    return len(changes)


async def run_forever(
    settings: Settings,
    storage: MonitorStorage,
    scanner: PlaywrightScanner,
    notifier: Notifier,
    stop_event: asyncio.Event | None = None,
) -> None:
    stop_event = stop_event or asyncio.Event()
    while not stop_event.is_set():
        try:
            await run_once(settings, storage, scanner, notifier)
        except Exception:
            LOG.exception("scan failed; stored appointment snapshot was left untouched")
        if stop_event.is_set():
            break
        LOG.info("next scan in %s seconds", settings.monitor.interval_seconds)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.monitor.interval_seconds)
        except TimeoutError:
            continue
