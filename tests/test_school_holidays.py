from datetime import date
from pathlib import Path

from schloss_monitor.school_holidays import annotations_for_dates, parse_school_holidays

FIXTURE = Path(__file__).parent / "fixtures" / "school_holidays.html"


def test_school_holidays_are_parsed_from_year_table_including_cross_year_range() -> None:
    calendar = parse_school_holidays(FIXTURE.read_text(encoding="utf-8"), "sachsen-anhalt")

    assert calendar.names_for(date(2026, 10, 24)) == ("Herbstferien",)
    assert calendar.names_for(date(2027, 1, 2)) == ("Weihnachtsferien",)
    assert calendar.names_for(date(2026, 11, 14)) == ()


def test_annotations_mark_public_holidays_for_configured_state() -> None:
    calendar = parse_school_holidays(FIXTURE.read_text(encoding="utf-8"), "sachsen-anhalt")

    annotations = annotations_for_dates([date(2027, 1, 6)], calendar)

    assert annotations[date(2027, 1, 6)].labels == ("FEIERTAG: Heilige Drei Könige",)


def test_annotations_mark_weekends_and_school_holidays_separately() -> None:
    calendar = parse_school_holidays(FIXTURE.read_text(encoding="utf-8"), "sachsen-anhalt")
    annotations = annotations_for_dates(
        [date(2026, 10, 24), date(2026, 10, 26), date(2026, 11, 14)], calendar
    )

    assert annotations[date(2026, 10, 24)].labels == ("WOCHENENDE", "SCHULFERIEN: Herbstferien")
    assert annotations[date(2026, 10, 26)].labels == ("SCHULFERIEN: Herbstferien",)
    assert annotations[date(2026, 11, 14)].labels == ("WOCHENENDE",)
