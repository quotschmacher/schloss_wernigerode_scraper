from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ..models import Appointment, Change


class Notifier(Protocol):
    def report_slots(self, appointments: Sequence[Appointment]) -> None: ...

    def notify(self, changes: Sequence[Change]) -> None: ...
