from __future__ import annotations

from pathlib import Path

import pytest

from schloss_monitor.calendar_scraper import (
    CalendarLoadError,
    load_more_until_complete,
    parse_calendar_entries,
    wait_for_calendar_progress,
)

FIXTURE = Path(__file__).parent / "fixtures" / "calendar_page.html"


def test_calendar_parser_uses_year_from_detail_url_and_marks_overview_sold_out() -> None:
    entries = parse_calendar_entries(
        FIXTURE.read_text(encoding="utf-8"),
        "https://www.schloss-wernigerode.de/kalender/die-schule-der-magischen-tiere",
    )

    assert [entry.event_date.isoformat() for entry in entries] == ["2026-10-19", "2026-10-20", "2026-11-10"]
    assert entries[0].overview_sold_out is True
    assert entries[1].overview_sold_out is False
    assert entries[2].detail_url == (
        "https://www.schloss-wernigerode.de/kalender/detail/die-schule-der-magischen-tiere/10-11-2026"
    )


class FakeLoader:
    def __init__(self, counts: list[int], visible: list[bool]) -> None:
        self.counts = counts
        self.visible = visible
        self.position = 0
        self.clicks = 0

    async def count(self) -> int:
        return self.counts[self.position]

    async def button_visible(self) -> bool:
        return self.visible[self.position]

    async def click(self) -> None:
        self.clicks += 1
        self.position += 1

    async def wait_for_progress(self, previous_count: int) -> bool:
        return await self.count() > previous_count or not await self.button_visible()


@pytest.mark.asyncio
async def test_load_more_waits_for_new_entries_and_stops_when_button_disappears() -> None:
    loader = FakeLoader(counts=[7, 14, 14], visible=[True, True, False])

    loaded_count = await load_more_until_complete(
        loader.count, loader.button_visible, loader.click, loader.wait_for_progress, max_clicks=5
    )

    assert loaded_count == 14
    assert loader.clicks == 2


@pytest.mark.asyncio
async def test_load_more_stagnation_is_a_failed_scan() -> None:
    loader = FakeLoader(counts=[7, 7], visible=[True, True])

    with pytest.raises(CalendarLoadError, match="did not add entries"):
        await load_more_until_complete(
            loader.count, loader.button_visible, loader.click, loader.wait_for_progress, max_clicks=5
        )


class KeywordOnlyWaitPage:
    def __init__(self) -> None:
        self.argument: int | None = None

    async def wait_for_function(self, expression: str, *, arg: int, timeout: int) -> None:
        assert "eventLink" in expression
        assert timeout == 123
        self.argument = arg


@pytest.mark.asyncio
async def test_calendar_progress_wait_uses_playwright_keyword_argument() -> None:
    page = KeywordOnlyWaitPage()

    assert await wait_for_calendar_progress(page, previous_count=7, timeout_ms=123) is True
    assert page.argument == 7
