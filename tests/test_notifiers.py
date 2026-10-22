from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from schloss_monitor.models import Appointment, AppointmentStatus, Change, ChangeType, CountSource
from schloss_monitor.notifiers.console import ConsoleNotifier
from schloss_monitor.notifiers.telegram import TelegramNotifier
from schloss_monitor.school_holidays import SlotAnnotation


def make_change(count: int | None) -> Change:
    appointment = Appointment(
        event_key="magische-tiere-2026-11-10-1130",
        start_at=datetime(2026, 11, 10, 11, 30, tzinfo=ZoneInfo("Europe/Berlin")),
        status=AppointmentStatus.AVAILABLE,
        available_places=count,
        detail_url="https://example.test/detail",
        booking_url="https://example.test/booking",
        observed_at=datetime.now(ZoneInfo("UTC")),
        count_source=CountSource.UNKNOWN if count is None else CountSource.TICKETFRITZ_EXACT,
    )
    return Change(ChangeType.NEW, appointment)


def test_console_notifier_marks_unknown_counts_explicitly(capsys) -> None:
    ConsoleNotifier().notify([make_change(None)])

    assert "ANZAHL UNBEKANNT" in capsys.readouterr().out


def test_console_reports_free_slots_on_every_successful_scan(capsys) -> None:
    notifier = ConsoleNotifier()
    appointment = make_change(5).appointment
    notifier.report_slots(
        [appointment, make_change(None).appointment],
        {appointment.event_key: SlotAnnotation(True, ("Herbstferien",))},
    )

    output = capsys.readouterr().out
    assert "[FREI] 10.11.2026 11:30 – 5 Plätze frei" in output
    assert "[WOCHENENDE | SCHULFERIEN: Herbstferien]" in output
    assert "[FREI] 10.11.2026 11:30 – buchbar, exakte Platzzahl nicht ermittelbar" in output


def test_disabled_telegram_notifier_is_a_noop() -> None:
    assert TelegramNotifier(enabled=False).notify([make_change(5)]) is None
