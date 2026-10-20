from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .models import CalendarEntry


class CalendarLoadError(RuntimeError):
    """Raised when the calendar cannot be proven complete."""


_DATE_FROM_DETAIL_URL = re.compile(r"/(\d{2})-(\d{2})-(\d{4})/?(?:[?#].*)?$")


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def _date_from_url(detail_url: str) -> date:
    match = _DATE_FROM_DETAIL_URL.search(detail_url)
    if not match:
        raise CalendarLoadError(f"detail URL has no unambiguous date: {detail_url}")
    day, month, year = (int(part) for part in match.groups())
    return date(year, month, day)


def parse_calendar_entries(html: str, base_url: str) -> list[CalendarEntry]:
    """Parse calendar cards using the observed `a.eventLink` structure."""
    soup = BeautifulSoup(html, "html.parser")
    entries: list[CalendarEntry] = []
    seen_urls: set[str] = set()
    for link in soup.select("#eventlist a.eventLink[href]"):
        detail_url = urljoin(base_url, str(link["href"]))
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        card = link.select_one(".event") or link
        label = card.select_one(".label")
        title = card.select_one(".eckdaten h2")
        times = card.select_one(".uhrzeiten")
        entries.append(
            CalendarEntry(
                event_date=_date_from_url(detail_url),
                title=title.get_text(" ", strip=True) if title else "",
                detail_url=detail_url,
                overview_sold_out=bool(label and "leider ausgebucht" in _normalize(label.get_text(" "))),
                overview_times=times.get_text(" ", strip=True) if times else "",
            )
        )
    return entries


async def load_more_until_complete(
    count_entries: Callable[[], Awaitable[int]],
    button_visible: Callable[[], Awaitable[bool]],
    click_button: Callable[[], Awaitable[None]],
    wait_for_progress: Callable[[int], Awaitable[bool]],
    *,
    max_clicks: int,
) -> int:
    """Click load-more only while each click creates measurable progress."""
    clicks = 0
    while await button_visible():
        if clicks >= max_clicks:
            raise CalendarLoadError(f"load-more limit ({max_clicks}) reached")
        before = await count_entries()
        await click_button()
        clicks += 1
        if not await wait_for_progress(before):
            raise CalendarLoadError("load-more did not add entries or disappear")
    return await count_entries()


async def wait_for_calendar_progress(page: Page, previous_count: int, timeout_ms: int) -> bool:
    try:
        await page.wait_for_function(
            """previous => document.querySelectorAll('#eventlist a.eventLink').length > previous
            || !document.querySelector('#weitereTermineLaden')""",
            arg=previous_count,
            timeout=timeout_ms,
        )
    except PlaywrightTimeoutError:
        return False
    return True


class CalendarScraper:
    def __init__(self, url: str, timeout_ms: int, max_load_more_clicks: int) -> None:
        self.url = url
        self.timeout_ms = timeout_ms
        self.max_load_more_clicks = max_load_more_clicks

    async def discover(self, page: Page) -> list[CalendarEntry]:
        await page.goto(self.url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        await self._confirm_necessary_cookies(page)
        event_links = page.locator("#eventlist a.eventLink")
        button = page.locator("#weitereTermineLaden")

        async def button_visible() -> bool:
            return await button.count() > 0 and await button.is_visible()

        async def wait_for_progress(previous_count: int) -> bool:
            return await wait_for_calendar_progress(page, previous_count, self.timeout_ms)

        await load_more_until_complete(
            event_links.count,
            button_visible,
            button.click,
            wait_for_progress,
            max_clicks=self.max_load_more_clicks,
        )
        return parse_calendar_entries(await page.content(), self.url)

    async def _confirm_necessary_cookies(self, page: Page) -> None:
        button = page.get_by_role("button", name="Nur Auswahl bestätigen")
        if await button.count() and await button.is_visible():
            await button.click(no_wait_after=True)
