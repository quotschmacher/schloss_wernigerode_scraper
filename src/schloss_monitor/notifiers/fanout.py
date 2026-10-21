from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..models import Appointment, Change
from .base import Notifier


@dataclass(frozen=True)
class FanoutNotifier:
    notifiers: Sequence[Notifier]

    def report_slots(self, appointments: Sequence[Appointment]) -> None:
        for notifier in self.notifiers:
            notifier.report_slots(appointments)

    def notify(self, changes: Sequence[Change]) -> None:
        for notifier in self.notifiers:
            notifier.notify(changes)
