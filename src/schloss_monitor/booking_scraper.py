from __future__ import annotations

import json
from datetime import datetime

from .models import AppointmentStatus, Availability, CountSource


def _matches_start(event: dict[str, object], expected_start: datetime) -> bool:
    display = event.get("ZeitpunktBezeichnung")
    expected = expected_start.strftime("%d.%m.%Y - %H:%M")
    return isinstance(display, str) and display.strip() == expected


def parse_ticketfritz_availability(payload: str, expected_start: datetime) -> Availability:
    """Read only explicit availability fields from Ticketfritz's observed response."""
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return Availability(AppointmentStatus.UNKNOWN, None, CountSource.UNKNOWN)
    events = decoded.get("data") if isinstance(decoded, dict) else None
    if not isinstance(events, list):
        return Availability(AppointmentStatus.UNKNOWN, None, CountSource.UNKNOWN)
    for event in events:
        if not isinstance(event, dict) or not _matches_start(event, expected_start):
            continue
        if event.get("Ausverkauft") is True:
            return Availability(AppointmentStatus.SOLD_OUT, 0, CountSource.TICKETFRITZ_SOLD_OUT)
        for field in ("AnzahlFrei", "MengeAktuellVerfuegbar"):
            value = event.get(field)
            if isinstance(value, int) and value >= 0:
                return Availability(AppointmentStatus.AVAILABLE, value, CountSource.TICKETFRITZ_EXACT)
        return Availability(AppointmentStatus.AVAILABLE, None, CountSource.UNKNOWN)
    return Availability(AppointmentStatus.UNKNOWN, None, CountSource.UNKNOWN)
