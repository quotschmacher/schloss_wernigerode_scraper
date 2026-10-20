from __future__ import annotations

from collections.abc import Sequence

from ..models import Appointment, AppointmentStatus, Change, ChangeType


class ConsoleNotifier:
    def report_slots(self, appointments: Sequence[Appointment]) -> None:
        available = sorted(
            (appointment for appointment in appointments if appointment.status is AppointmentStatus.AVAILABLE),
            key=lambda appointment: appointment.start_at,
        )
        if not available:
            print("[FREI] keine freien Termine gefunden", flush=True)
            return
        for appointment in available:
            when = appointment.start_at.strftime("%d.%m.%Y %H:%M")
            if appointment.available_places is None:
                print(
                    f"[FREI] {when} – buchbar, exakte Platzzahl nicht ermittelbar – "
                    f"{appointment.booking_url}",
                    flush=True,
                )
            else:
                print(
                    f"[FREI] {when} – {appointment.available_places} Plätze frei – "
                    f"{appointment.booking_url}",
                    flush=True,
                )

    def notify(self, changes: Sequence[Change]) -> None:
        for change in changes:
            print(self.render(change), flush=True)

    @staticmethod
    def render(change: Change) -> str:
        item = change.appointment
        when = item.start_at.strftime("%d.%m.%Y %H:%M")
        if change.kind is ChangeType.NEW and item.available_places is None:
            return f"[ANZAHL UNBEKANNT] {when} – buchbar, exakte Platzzahl nicht ermittelbar – {item.booking_url}"
        if change.kind is ChangeType.NEW:
            return f"[NEU] {when} – {item.available_places} Plätze frei – {item.booking_url}"
        if change.kind is ChangeType.INCREASED:
            return f"[MEHR] {when} – {change.previous_available_places} → {item.available_places} Plätze"
        if change.kind is ChangeType.DECREASED:
            return f"[WENIGER] {when} – {change.previous_available_places} → {item.available_places} Plätze"
        if change.kind is ChangeType.COUNT_DISCOVERED:
            return f"[ANZAHL ERMITTELT] {when} – ? → {item.available_places} Plätze"
        if change.kind is ChangeType.COUNT_UNKNOWN:
            return f"[ANZAHL UNBEKANNT] {when} – aktueller Wert nicht sicher lesbar"
        if change.kind is ChangeType.SOLD_OUT:
            return f"[AUSGEBUCHT] {when} – 0 Plätze"
        return f"[ENTFALLEN/UNGEPRÜFT] {when}"
