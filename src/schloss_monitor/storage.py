from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .models import Appointment, AppointmentStatus, Change, ChangeType, CountSource


class MonitorStorage:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                event_key TEXT PRIMARY KEY,
                start_at TEXT NOT NULL,
                status TEXT NOT NULL,
                available_places INTEGER NULL,
                detail_url TEXT NOT NULL,
                booking_url TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                count_source TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_changed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scan_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                completed_at TEXT NULL,
                status TEXT NOT NULL,
                calendar_days INTEGER NOT NULL DEFAULT 0,
                slots_examined INTEGER NOT NULL DEFAULT 0,
                error_message TEXT NULL
            );
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def current_appointments(self) -> dict[str, Appointment]:
        rows = self.connection.execute("SELECT * FROM appointments ORDER BY start_at").fetchall()
        return {row["event_key"]: self._appointment_from_row(row) for row in rows}

    def record_failed_scan(self, error_message: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connection:
            self.connection.execute(
                "INSERT INTO scan_runs (started_at, completed_at, status, error_message) VALUES (?, ?, ?, ?)",
                (now, now, "FAILED", error_message),
            )

    def commit_successful_scan(
        self, appointments: list[Appointment], protected_dates: set[str] | None = None
    ) -> list[Change]:
        current = {appointment.event_key: appointment for appointment in appointments}
        previous = self.current_appointments()
        for key, appointment in previous.items():
            if appointment.start_at.date().isoformat() in (protected_dates or set()) and key not in current:
                current[key] = appointment
        changes = self._changes(previous, current)
        now = datetime.now(UTC).isoformat()
        with self.connection:
            self.connection.execute(
                "INSERT INTO scan_runs (started_at, completed_at, status, slots_examined) VALUES (?, ?, ?, ?)",
                (now, now, "SUCCESS", len(appointments)),
            )
            self.connection.execute("DELETE FROM appointments")
            for appointment in sorted(appointments, key=lambda item: item.start_at):
                old = previous.get(appointment.event_key)
                changed = old != appointment
                self.connection.execute(
                    """
                    INSERT INTO appointments (
                        event_key, start_at, status, available_places, detail_url, booking_url,
                        observed_at, count_source, first_seen_at, last_changed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        appointment.event_key,
                        appointment.start_at.isoformat(),
                        appointment.status.value,
                        appointment.available_places,
                        appointment.detail_url,
                        appointment.booking_url,
                        appointment.observed_at.astimezone(UTC).isoformat(),
                        appointment.count_source.value,
                        old.observed_at.astimezone(UTC).isoformat() if old else now,
                        now if changed else (old.observed_at.astimezone(UTC).isoformat() if old else now),
                    ),
                )
        return changes

    @staticmethod
    def _changes(previous: dict[str, Appointment], current: dict[str, Appointment]) -> list[Change]:
        changes: list[Change] = []
        for key, appointment in sorted(current.items()):
            old = previous.get(key)
            if old is None:
                if appointment.status is AppointmentStatus.AVAILABLE:
                    changes.append(Change(ChangeType.NEW, appointment))
                continue
            if appointment.status is AppointmentStatus.SOLD_OUT and old.status is not AppointmentStatus.SOLD_OUT:
                changes.append(Change(ChangeType.SOLD_OUT, appointment, old.available_places))
                continue
            if appointment.status is not AppointmentStatus.AVAILABLE or old.status is not AppointmentStatus.AVAILABLE:
                continue
            if old.available_places is None and appointment.available_places is not None:
                changes.append(Change(ChangeType.COUNT_DISCOVERED, appointment, None))
            elif old.available_places is not None and appointment.available_places is None:
                changes.append(Change(ChangeType.COUNT_UNKNOWN, appointment, old.available_places))
            elif old.available_places is not None and appointment.available_places is not None:
                if appointment.available_places > old.available_places:
                    changes.append(Change(ChangeType.INCREASED, appointment, old.available_places))
                elif appointment.available_places < old.available_places:
                    changes.append(Change(ChangeType.DECREASED, appointment, old.available_places))
        for key, appointment in sorted(previous.items()):
            if key not in current:
                changes.append(Change(ChangeType.NO_LONGER_LISTED, appointment, appointment.available_places))
        return changes

    @staticmethod
    def _appointment_from_row(row: sqlite3.Row) -> Appointment:
        return Appointment(
            event_key=row["event_key"],
            start_at=datetime.fromisoformat(row["start_at"]),
            status=AppointmentStatus(row["status"]),
            available_places=row["available_places"],
            detail_url=row["detail_url"],
            booking_url=row["booking_url"],
            observed_at=datetime.fromisoformat(row["observed_at"]),
            count_source=CountSource(row["count_source"]),
        )
