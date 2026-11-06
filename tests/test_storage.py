from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from schloss_monitor.models import Appointment, AppointmentStatus, ChangeType, CountSource
from schloss_monitor.school_holidays import SlotAnnotation
from schloss_monitor.storage import MonitorStorage, StorageError

UTC = ZoneInfo("UTC")
BERLIN = ZoneInfo("Europe/Berlin")


def appointment(key: str, count: int | None, status: AppointmentStatus = AppointmentStatus.AVAILABLE) -> Appointment:
    return Appointment(
        event_key=key,
        start_at=datetime(2026, 11, 10, int(key[-2:]), 30, tzinfo=BERLIN),
        status=status,
        available_places=count,
        detail_url="https://example.test/detail",
        booking_url="https://example.test/booking",
        observed_at=datetime(2026, 10, 19, 20, 0, tzinfo=UTC),
        count_source=CountSource.TICKETFRITZ_EXACT if count is not None else CountSource.UNKNOWN,
    )


def test_storage_rejects_a_database_path_mounted_as_a_directory(tmp_path: Path) -> None:
    database = tmp_path / "appointments.sqlite3"
    database.mkdir()

    with pytest.raises(StorageError, match="Mount the containing directory"):
        MonitorStorage(database)


def test_storage_persists_only_successful_scans_and_emits_deltas(tmp_path: Path) -> None:
    database = tmp_path / "appointments.sqlite3"
    storage = MonitorStorage(database)
    first = [appointment("magische-tiere-2026-11-10-11", 5), appointment("magische-tiere-2026-11-10-14", None)]

    assert [change.kind for change in storage.commit_successful_scan(first)] == [ChangeType.NEW, ChangeType.NEW]
    assert storage.commit_successful_scan(first) == []

    changed = storage.commit_successful_scan(
        [
            appointment("magische-tiere-2026-11-10-11", 3),
            appointment("magische-tiere-2026-11-10-14", 4),
            appointment("magische-tiere-2026-11-11-11", 2),
        ]
    )
    assert [change.kind for change in changed] == [ChangeType.DECREASED, ChangeType.COUNT_DISCOVERED, ChangeType.NEW]

    storage.record_failed_scan("calendar pagination stalled")
    assert storage.current_appointments()["magische-tiere-2026-11-10-11"].available_places == 3

    absent = storage.commit_successful_scan([appointment("magische-tiere-2026-11-10-11", 3)])
    assert [change.kind for change in absent] == [ChangeType.NO_LONGER_LISTED, ChangeType.NO_LONGER_LISTED]
    storage.close()

    reopened = MonitorStorage(database)
    assert set(reopened.current_appointments()) == {"magische-tiere-2026-11-10-11"}
    reopened.close()


def test_storage_persists_telegram_update_offset(tmp_path: Path) -> None:
    database = tmp_path / "appointments.sqlite3"
    storage = MonitorStorage(database)

    assert storage.telegram_update_offset() is None
    storage.set_telegram_update_offset(42)
    assert storage.telegram_update_offset() == 42
    storage.close()

    reopened = MonitorStorage(database)
    assert reopened.telegram_update_offset() == 42
    reopened.close()


def test_storage_persists_calendar_annotations_for_database_lists(tmp_path: Path) -> None:
    storage = MonitorStorage(tmp_path / "appointments.sqlite3")
    item = appointment("magische-tiere-2026-11-10-11", 5)
    annotations = {item.event_key: SlotAnnotation(True, ("Herbstferien",))}

    storage.commit_successful_scan([item], annotations=annotations)

    assert storage.current_annotations() == annotations
    storage.close()
