from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..models import Appointment, Change


@dataclass(frozen=True)
class TelegramNotifier:
    """Reserved for a future release; deliberately performs no network I/O."""

    enabled: bool = False

    def report_slots(self, appointments: Sequence[Appointment]) -> None:
        del appointments
        return None

    def notify(self, changes: Sequence[Change]) -> None:
        del changes
        # Telegram is intentionally disabled even if configuration says enabled.
        return None
