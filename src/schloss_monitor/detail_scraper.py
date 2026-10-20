from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .models import DetailSlot

BERLIN = ZoneInfo("Europe/Berlin")
_DATE_FROM_URL = re.compile(r"/(\d{2})-(\d{2})-(\d{4})/?(?:[?#].*)?$")
_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b")


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def _date_from_detail_url(detail_url: str) -> tuple[int, int, int]:
    match = _DATE_FROM_URL.search(detail_url)
    if not match:
        raise ValueError(f"detail URL has no date: {detail_url}")
    day, month, year = (int(value) for value in match.groups())
    return year, month, day


def parse_detail_slots(html: str, detail_url: str) -> list[DetailSlot]:
    """Return only individual, currently bookable blocks from a detail page."""
    soup = BeautifulSoup(html, "html.parser")
    year, month, day = _date_from_detail_url(detail_url)
    slots: list[DetailSlot] = []
    for block in soup.select("#eventTermine .eventTermin"):
        status = _normalized(block.select_one(".plaetze").get_text(" ", strip=True)) if block.select_one(".plaetze") else ""
        booking = block.select_one("a.buchen[href]")
        time = block.select_one(".uhrzeit")
        if "noch plätze frei" not in status or booking is None or time is None:
            continue
        match = _TIME.search(time.get_text(" ", strip=True))
        if match is None:
            continue
        hour, minute = (int(value) for value in match.groups())
        slots.append(
            DetailSlot(
                start_at=datetime(year, month, day, hour, minute, tzinfo=BERLIN),
                booking_url=urljoin(detail_url, str(booking["href"])),
            )
        )
    return sorted(slots, key=lambda slot: slot.start_at)
