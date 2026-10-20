from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class AppointmentStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    SOLD_OUT = "SOLD_OUT"
    UNKNOWN = "UNKNOWN"


class CountSource(StrEnum):
    TICKETFRITZ_EXACT = "ticketfritz_get_events"
    UNKNOWN = "unknown"
    TICKETFRITZ_SOLD_OUT = "ticketfritz_sold_out"


class ChangeType(StrEnum):
    NEW = "NEW"
    INCREASED = "INCREASED"
    DECREASED = "DECREASED"
    SOLD_OUT = "SOLD_OUT"
    NO_LONGER_LISTED = "NO_LONGER_LISTED"
    COUNT_DISCOVERED = "COUNT_DISCOVERED"
    COUNT_UNKNOWN = "COUNT_UNKNOWN"


@dataclass(frozen=True)
class CalendarEntry:
    event_date: date
    title: str
    detail_url: str
    overview_sold_out: bool
    overview_times: str


@dataclass(frozen=True)
class DetailSlot:
    start_at: datetime
    booking_url: str


@dataclass(frozen=True)
class Availability:
    status: AppointmentStatus
    available_places: int | None
    source: CountSource


@dataclass(frozen=True)
class Appointment:
    event_key: str
    start_at: datetime
    status: AppointmentStatus
    available_places: int | None
    detail_url: str
    booking_url: str
    observed_at: datetime
    count_source: CountSource


@dataclass(frozen=True)
class Change:
    kind: ChangeType
    appointment: Appointment
    previous_available_places: int | None = None
