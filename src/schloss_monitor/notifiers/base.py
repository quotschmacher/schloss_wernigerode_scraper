from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from ..models import Appointment, Change
from ..school_holidays import SlotAnnotation


class Notifier(Protocol):
    def report_slots(
        self, appointments: Sequence[Appointment], annotations: Mapping[str, SlotAnnotation] | None = None
    ) -> None: ...

    def notify(
        self, changes: Sequence[Change], annotations: Mapping[str, SlotAnnotation] | None = None
    ) -> None: ...
