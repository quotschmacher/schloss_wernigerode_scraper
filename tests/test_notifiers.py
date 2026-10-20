from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from schloss_monitor.models import Appointment, AppointmentStatus, Change, ChangeType, CountSource
from schloss_monitor.notifiers.console import ConsoleNotifier
from schloss_monitor.notifiers.telegram import TelegramNotifier


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
    notifier.report_slots([make_change(5).appointment, make_change(None).appointment])

    output = capsys.readouterr().out
    assert "[FREI] 10.11.2026 11:30 – 5 Plätze frei" in output
    assert "[FREI] 10.11.2026 11:30 – buchbar, exakte Platzzahl nicht ermittelbar" in output


def test_telegram_notifier_is_an_explicit_noop() -> None:
    assert TelegramNotifier(enabled=True).notify([make_change(5)]) is None
