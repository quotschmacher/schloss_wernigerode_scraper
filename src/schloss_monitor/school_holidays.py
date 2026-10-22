from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

_DATE_TOKEN = re.compile(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\.?" )
_HOLIDAY_NAMES = {
    "Winter": "Winterferien",
    "Ostern": "Osterferien",
    "Pfingsten": "Pfingstferien",
    "Sommer": "Sommerferien",
    "Herbst": "Herbstferien",
    "Weihnachten": "Weihnachtsferien",
}


@dataclass(frozen=True)
class HolidayRange:
    name: str
    start: date
    end: date


@dataclass(frozen=True)
class SlotAnnotation:
    is_weekend: bool
    holiday_names: tuple[str, ...]

    @property
    def labels(self) -> tuple[str, ...]:
        labels: list[str] = []
        if self.is_weekend:
            labels.append("WOCHENENDE")
        labels.extend(f"SCHULFERIEN: {name}" for name in self.holiday_names)
        return tuple(labels)


@dataclass(frozen=True)
class SchoolHolidayCalendar:
    federal_state: str
    ranges: tuple[HolidayRange, ...]

    def names_for(self, value: date) -> tuple[str, ...]:
        return tuple(holiday.name for holiday in self.ranges if holiday.start <= value <= holiday.end)


class SchoolHolidayError(RuntimeError):
    """School holiday data could not be retrieved or parsed."""


def _as_date(day: str, month: str, year: str | None, default_year: int) -> date:
    return date(int(year) if year else default_year, int(month), int(day))


def _ranges_from_cell(value: str, row_year: int, name: str) -> list[HolidayRange]:
    ranges: list[HolidayRange] = []
    for segment in value.split("+"):
        tokens = _DATE_TOKEN.findall(segment)
        if not tokens:
            continue
        start = _as_date(*tokens[0], row_year)
        if len(tokens) == 1:
            end = start
        else:
            end = _as_date(*tokens[1], start.year)
            if not tokens[1][2] and end < start:
                end = date(start.year + 1, end.month, end.day)
        ranges.append(HolidayRange(name, start, end))
    return ranges


def parse_school_holidays(html: str, federal_state: str) -> SchoolHolidayCalendar:
    """Parse the observed annual holiday table from schulferien.org."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.sf_table")
    if table is None:
        raise SchoolHolidayError("holiday year table not found")
    headers = [header.get_text(" ", strip=True) for header in table.select("thead th")][1:]
    holiday_names = [_HOLIDAY_NAMES.get(header, header) for header in headers]
    ranges: list[HolidayRange] = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        year_match = re.search(r"\b(\d{4})\b", cells[0].get_text(" ", strip=True))
        if year_match is None:
            continue
        row_year = int(year_match.group(1))
        for name, cell in zip(holiday_names, cells[1:], strict=False):
            ranges.extend(_ranges_from_cell(cell.get_text(" ", strip=True), row_year, name))
    if not ranges:
        raise SchoolHolidayError("no holiday ranges parsed")
    return SchoolHolidayCalendar(federal_state=federal_state, ranges=tuple(ranges))


def annotations_for_dates(
    values: list[date], calendar: SchoolHolidayCalendar
) -> dict[date, SlotAnnotation]:
    return {
        value: SlotAnnotation(value.weekday() >= 5, calendar.names_for(value))
        for value in set(values)
    }


class SchoolHolidayProvider:
    def __init__(self, federal_state: str, timeout_seconds: float = 15.0) -> None:
        self.federal_state = federal_state
        self.timeout_seconds = timeout_seconds

    @property
    def url(self) -> str:
        return f"https://www.schulferien.org/deutschland/ferien/{self.federal_state}/"

    def annotations_for(self, values: list[date]) -> dict[date, SlotAnnotation]:
        request = Request(self.url, headers={"User-Agent": "SchlossTerminmonitor/0.1"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 -- configured fixed host
                html = response.read().decode("utf-8")
        except OSError as error:
            raise SchoolHolidayError(f"could not retrieve school holidays: {error}") from error
        return annotations_for_dates(values, parse_school_holidays(html, self.federal_state))
