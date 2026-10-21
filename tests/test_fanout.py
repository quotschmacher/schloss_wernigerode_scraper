from datetime import datetime
from zoneinfo import ZoneInfo

from schloss_monitor.models import Appointment, AppointmentStatus, Change, ChangeType, CountSource
from schloss_monitor.notifiers.fanout import FanoutNotifier


class RecordingNotifier:
    def __init__(self) -> None:
        self.slot_calls = 0
        self.change_calls = 0

    def report_slots(self, appointments) -> None:
        assert appointments
        self.slot_calls += 1

    def notify(self, changes) -> None:
        assert changes
        self.change_calls += 1


def test_fanout_forwards_slot_reports_and_changes() -> None:
    appointment = Appointment(
        event_key="magische-tiere-2026-11-10-1130",
        start_at=datetime(2026, 11, 10, 11, 30, tzinfo=ZoneInfo("Europe/Berlin")),
        status=AppointmentStatus.AVAILABLE,
        available_places=5,
        detail_url="https://example.test/detail",
        booking_url="https://example.test/booking",
        observed_at=datetime.now(ZoneInfo("UTC")),
        count_source=CountSource.TICKETFRITZ_EXACT,
    )
    first = RecordingNotifier()
    second = RecordingNotifier()
    notifier = FanoutNotifier([first, second])

    notifier.report_slots([appointment])
    notifier.notify([Change(ChangeType.NEW, appointment)])

    assert (first.slot_calls, first.change_calls) == (1, 1)
    assert (second.slot_calls, second.change_calls) == (1, 1)
