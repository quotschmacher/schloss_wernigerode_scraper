from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..models import Appointment, AppointmentStatus, Change, ChangeType
from ..school_holidays import SlotAnnotation


class ConsoleNotifier:
    def report_slots(
        self, appointments: Sequence[Appointment], annotations: Mapping[str, SlotAnnotation] | None = None
    ) -> None:
        annotations = annotations or {}
        available = sorted(
            (appointment for appointment in appointments if appointment.status is AppointmentStatus.AVAILABLE),
            key=lambda appointment: appointment.start_at,
        )
        if not available:
            print("[FREI] keine freien Termine gefunden", flush=True)
            return
        for appointment in available:
            when = appointment.start_at.strftime("%d.%m.%Y %H:%M")
            markers = self._marker_suffix(annotations.get(appointment.event_key))
            if appointment.available_places is None:
                print(
                    f"[FREI] {when} – buchbar, exakte Platzzahl nicht ermittelbar{markers} – "
                    f"{appointment.booking_url}",
                    flush=True,
                )
            else:
                print(
                    f"[FREI] {when} – {appointment.available_places} Plätze frei{markers} – "
                    f"{appointment.booking_url}",
                    flush=True,
                )

    @staticmethod
    def _marker_suffix(annotation: SlotAnnotation | None) -> str:
        if annotation is None or not annotation.labels:
            return ""
        return f" [{' | '.join(annotation.labels)}]"

    def notify(
        self, changes: Sequence[Change], annotations: Mapping[str, SlotAnnotation] | None = None
    ) -> None:
        annotations = annotations or {}
        for change in changes:
            print(self.render(change, annotations.get(change.appointment.event_key)), flush=True)

    @staticmethod
    def render(change: Change, annotation: SlotAnnotation | None = None) -> str:
        item = change.appointment
        when = item.start_at.strftime("%d.%m.%Y %H:%M")
        markers = ConsoleNotifier._marker_suffix(annotation)
        if change.kind is ChangeType.NEW and item.available_places is None:
            return f"[ANZAHL UNBEKANNT] {when}{markers} – buchbar, exakte Platzzahl nicht ermittelbar – {item.booking_url}"
        if change.kind is ChangeType.NEW:
            return f"[NEU] {when}{markers} – {item.available_places} Plätze frei – {item.booking_url}"
        if change.kind is ChangeType.INCREASED:
            return f"[MEHR] {when}{markers} – {change.previous_available_places} → {item.available_places} Plätze"
        if change.kind is ChangeType.DECREASED:
            return f"[WENIGER] {when}{markers} – {change.previous_available_places} → {item.available_places} Plätze"
        if change.kind is ChangeType.COUNT_DISCOVERED:
            return f"[ANZAHL ERMITTELT] {when}{markers} – ? → {item.available_places} Plätze"
        if change.kind is ChangeType.COUNT_UNKNOWN:
            return f"[ANZAHL UNBEKANNT] {when}{markers} – aktueller Wert nicht sicher lesbar"
        if change.kind is ChangeType.SOLD_OUT:
            return f"[AUSGEBUCHT] {when}{markers} – 0 Plätze"
        return f"[ENTFALLEN/UNGEPRÜFT] {when}{markers}"
