from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from schloss_monitor.booking_scraper import parse_ticketfritz_availability
from schloss_monitor.detail_scraper import parse_detail_slots
from schloss_monitor.models import AppointmentStatus, CountSource


def test_detail_parser_keeps_booking_link_with_its_own_time() -> None:
    html = (Path(__file__).parent / "fixtures" / "detail_mixed.html").read_text(encoding="utf-8")

    slots = parse_detail_slots(html, "https://www.schloss-wernigerode.de/kalender/detail/die-schule-der-magischen-tiere/10-11-2026")

    assert [(slot.start_at.strftime("%Y-%m-%d %H:%M"), slot.booking_url) for slot in slots] == [
        ("2026-11-10 11:30", "https://schloss-wernigerode.ticketfritz.de/Event/Kalender/31935/59065?typ=Vorlage"),
        ("2026-11-10 14:00", "https://schloss-wernigerode.ticketfritz.de/Event/Kalender/31935/59066?typ=Vorlage"),
    ]
    assert all(slot.start_at.tzinfo == ZoneInfo("Europe/Berlin") for slot in slots)


def test_booking_response_uses_explicit_remaining_count_not_total_capacity() -> None:
    expected = datetime(2026, 11, 10, 11, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    payload = json.dumps(
        {"data": [{"ZeitpunktBezeichnung": "10.11.2026 - 11:30", "Ausverkauft": False, "AnzahlKapazitaet": 18, "AnzahlFrei": 5, "MengeAktuellVerfuegbar": 5}]}
    )

    result = parse_ticketfritz_availability(payload, expected)

    assert result.status is AppointmentStatus.AVAILABLE
    assert result.available_places == 5
    assert result.source is CountSource.TICKETFRITZ_EXACT


def test_booking_response_with_capacity_only_keeps_count_unknown() -> None:
    expected = datetime(2026, 11, 10, 11, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    payload = json.dumps(
        {"data": [{"ZeitpunktBezeichnung": "10.11.2026 - 11:30", "Ausverkauft": False, "AnzahlKapazitaet": 18, "CapacityTotal": 18}]}
    )

    result = parse_ticketfritz_availability(payload, expected)

    assert result.status is AppointmentStatus.AVAILABLE
    assert result.available_places is None
    assert result.source is CountSource.UNKNOWN


def test_booking_response_with_verified_sold_out_has_zero_count() -> None:
    expected = datetime(2026, 11, 10, 11, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    payload = json.dumps({"data": [{"ZeitpunktBezeichnung": "10.11.2026 - 11:30", "Ausverkauft": True}]})

    result = parse_ticketfritz_availability(payload, expected)

    assert result.status is AppointmentStatus.SOLD_OUT
    assert result.available_places == 0
