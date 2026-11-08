from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..models import Appointment, Change
from ..school_holidays import SlotAnnotation
from .base import Notifier


@dataclass(frozen=True)
class FanoutNotifier:
    notifiers: Sequence[Notifier]

    def report_slots(
        self, appointments: Sequence[Appointment], annotations: Mapping[str, SlotAnnotation] | None = None
    ) -> None:
        for notifier in self.notifiers:
            notifier.report_slots(appointments, annotations)

    def report_scan_error(self, error: str) -> None:
        for notifier in self.notifiers:
            notifier.report_scan_error(error)

    def notify(
        self, changes: Sequence[Change], annotations: Mapping[str, SlotAnnotation] | None = None
    ) -> None:
        for notifier in self.notifiers:
            notifier.notify(changes, annotations)
