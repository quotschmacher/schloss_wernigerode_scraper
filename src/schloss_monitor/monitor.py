from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .booking_scraper import parse_ticketfritz_availability
from .calendar_scraper import CalendarScraper
from .config import Settings
from .detail_scraper import parse_detail_slots
from .models import Appointment, AppointmentStatus, Availability, CountSource
from .notifiers.base import Notifier
from .school_holidays import SchoolHolidayError, SchoolHolidayProvider, SlotAnnotation
from .storage import MonitorStorage
from .telegram_commands import TelegramCommandClient, TelegramCommandKind

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
    annotations: dict[str, SlotAnnotation] = field(default_factory=dict)


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
                        availability = self._availability_for_detail_slot(
                            await self._booking_availability(booking_page, slot.booking_url, slot.start_at),
                            slot.start_at,
                        )
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
                annotations = await self._annotations(appointments)
                return ScanResult(appointments, protected_dates, len(entries), annotations)
            finally:
                await context.close()
                await browser.close()

    async def _annotations(self, appointments: list[Appointment]) -> dict[str, SlotAnnotation]:
        dates = [appointment.start_at.date() for appointment in appointments]
        fallback = {date_value: SlotAnnotation(date_value.weekday() >= 5, ()) for date_value in set(dates)}
        if not dates:
            return {}
        provider = SchoolHolidayProvider(self.settings.holidays.federal_state)
        try:
            by_date = await asyncio.to_thread(provider.annotations_for, dates)
        except SchoolHolidayError as error:
            LOG.warning("school holiday lookup failed state=%s reason=%s", self.settings.holidays.federal_state, error)
            by_date = fallback
        return {
            appointment.event_key: by_date.get(appointment.start_at.date(), fallback[appointment.start_at.date()])
            for appointment in appointments
        }

    @staticmethod
    def _availability_for_detail_slot(availability: Availability, start_at: datetime) -> Availability:
        if availability.status is not AppointmentStatus.UNKNOWN:
            return availability
        LOG.warning(
            "Ticketfritz did not verify exact availability; recording detail-page slot as available with unknown count "
            "start_at=%s",
            start_at.isoformat(),
        )
        return Availability(AppointmentStatus.AVAILABLE, None, CountSource.UNKNOWN)

    async def _booking_availability(self, page: Page, booking_url: str, start_at: datetime):
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
        parsed_booking_url = urlparse(booking_url)
        endpoint = f"{parsed_booking_url.scheme}://{parsed_booking_url.netloc}/Event/getEvents?{query}"

        async def fetch_availability() -> tuple[int, str]:
            response = await page.context.request.get(endpoint)
            return response.status, await response.text()

        status, body = await retry_async(
            fetch_availability,
            attempts=2,
            delay_seconds=self.settings.scraper.request_delay_seconds,
        )
        if status != 200:
            raise ScanError(f"Ticketfritz availability request failed for {start_at.isoformat()} status={status}")
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


async def poll_telegram_commands(storage: MonitorStorage, client: TelegramCommandClient) -> list[str]:
    offset = storage.telegram_update_offset()
    updates = await asyncio.to_thread(client.fetch_updates, offset)
    update_ids: list[int] = []
    for update in updates:
        update_id = update.get("update_id")
        if isinstance(update_id, int):
            update_ids.append(update_id)
    if update_ids:
        storage.set_telegram_update_offset(max(update_ids) + 1)
    scan_requesters: list[str] = []
    for command in client.parse_updates(updates):
        if command.kind is TelegramCommandKind.HELP:
            await asyncio.to_thread(client.send_help, command.chat_id)
        elif command.kind is TelegramCommandKind.SCAN:
            scan_requesters.append(command.chat_id)
    return scan_requesters


async def run_once(settings: Settings, storage: MonitorStorage, scanner: PlaywrightScanner, notifier: Notifier) -> int:
    try:
        result = await scanner.scan()
    except Exception as error:
        storage.record_failed_scan(str(error))
        raise
    notifier.report_slots(result.appointments, result.annotations)
    changes = storage.preview_successful_scan(result.appointments, result.protected_dates)
    notifier.notify(changes, result.annotations)
    storage.commit_successful_scan(result.appointments, result.protected_dates)
    available_slots = sum(
        appointment.status is AppointmentStatus.AVAILABLE for appointment in result.appointments
    )
    sold_out_slots = sum(
        appointment.status is AppointmentStatus.SOLD_OUT for appointment in result.appointments
    )
    LOG.info(
        "scan finished days=%s slots=%s available=%s sold_out=%s changes=%s",
        result.calendar_days,
        len(result.appointments),
        available_slots,
        sold_out_slots,
        len(changes),
    )
    return len(changes)


async def wait_for_next_scan(
    *,
    interval_seconds: int,
    command_poll_seconds: int,
    stop_event: asyncio.Event,
    storage: MonitorStorage,
    command_client: TelegramCommandClient | None,
) -> list[str]:
    deadline = asyncio.get_running_loop().time() + interval_seconds
    while not stop_event.is_set():
        if command_client is not None:
            scan_requesters = await poll_telegram_commands(storage, command_client)
            if scan_requesters:
                return scan_requesters
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return []
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=min(command_poll_seconds, remaining))
        except TimeoutError:
            continue
    return []


async def run_forever(
    settings: Settings,
    storage: MonitorStorage,
    scanner: PlaywrightScanner,
    notifier: Notifier,
    stop_event: asyncio.Event | None = None,
    command_client: TelegramCommandClient | None = None,
) -> None:
    stop_event = stop_event or asyncio.Event()
    scan_requesters: list[str] = []
    while not stop_event.is_set():
        try:
            changes = await run_once(settings, storage, scanner, notifier)
        except Exception as error:
            LOG.exception("scan failed; stored appointment snapshot was left untouched")
            if command_client is not None:
                for chat_id in set(scan_requesters):
                    await asyncio.to_thread(command_client.send_scan_failure, chat_id, str(error))
        else:
            if command_client is not None:
                for chat_id in set(scan_requesters):
                    await asyncio.to_thread(command_client.send_scan_result, chat_id, changes=changes)
        scan_requesters = []
        if stop_event.is_set():
            break
        LOG.info("next scan in %s seconds", settings.monitor.interval_seconds)
        scan_requesters = await wait_for_next_scan(
            interval_seconds=settings.monitor.interval_seconds,
            command_poll_seconds=settings.telegram.command_poll_seconds,
            stop_event=stop_event,
            storage=storage,
            command_client=command_client,
        )
