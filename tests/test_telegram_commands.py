from __future__ import annotations

import json
from urllib.parse import parse_qs

from schloss_monitor.telegram_commands import TelegramCommandClient, TelegramCommandKind


def test_telegram_command_client_fetches_updates_after_persisted_offset() -> None:
    requested: list[str] = []

    def transport(url: str) -> bytes:
        requested.append(url)
        return b'{"ok":true,"result":[{"update_id":42}]}'

    client = TelegramCommandClient(
        bot_token="test-token",
        chat_id="123456",
        transport=transport,
        post_transport=lambda url, body: b'{"ok":true,"result":true}',
    )

    assert client.fetch_updates(42) == [{"update_id": 42}]
    query = parse_qs(requested[0].split("?", 1)[1])
    assert query == {"offset": ["42"], "timeout": ["0"], "allowed_updates": ['["message"]']}


def test_telegram_command_client_sends_scan_completion_status() -> None:
    sent: list[tuple[str, bytes]] = []

    def post_transport(url: str, body: bytes) -> bytes:
        sent.append((url, body))
        return b'{"ok":true,"result":true}'

    client = TelegramCommandClient(bot_token="test-token", chat_id="123456", post_transport=post_transport)

    client.send_scan_result("123456", changes=3)
    client.send_scan_failure("123456", "Ticketfritz timeout")

    messages = [parse_qs(body.decode())["text"][0] for _, body in sent]
    assert messages == [
        "[OK] Manueller Scan abgeschlossen. Änderungen: 3.",
        "[FEHLER] Manueller Scan fehlgeschlagen: Ticketfritz timeout",
    ]


def test_telegram_command_client_registers_commands_sends_help_buttons_and_filters_chat() -> None:
    sent: list[tuple[str, bytes]] = []

    def post_transport(url: str, body: bytes) -> bytes:
        sent.append((url, body))
        return b'{"ok":true,"result":true}'

    client = TelegramCommandClient(
        bot_token="test-token",
        chat_id="123456",
        post_transport=post_transport,
    )

    client.register_commands()
    client.send_help("123456")
    commands = client.parse_updates(
        [
            {"update_id": 10, "message": {"chat": {"id": 123456}, "text": "/scan"}},
            {"update_id": 11, "message": {"chat": {"id": 999}, "text": "/list"}},
            {"update_id": 12, "message": {"chat": {"id": 123456}, "text": "/help@slot_monitor_bot"}},
        ]
    )

    assert [(command.kind, command.chat_id, command.update_id) for command in commands] == [
        (TelegramCommandKind.SCAN, "123456", 10),
        (TelegramCommandKind.HELP, "123456", 12),
    ]
    assert [url.rsplit("/", 1)[-1] for url, _ in sent] == ["setMyCommands", "sendMessage"]
    command_payload = parse_qs(sent[0][1].decode())
    assert [command["command"] for command in json.loads(command_payload["commands"][0])] == ["scan", "list", "help"]
    help_payload = parse_qs(sent[1][1].decode())
    assert "/scan" in help_payload["text"][0]
    keyboard = json.loads(help_payload["reply_markup"][0])
    assert keyboard["keyboard"] == [[{"text": "/scan"}, {"text": "/list"}], [{"text": "/help"}]]
