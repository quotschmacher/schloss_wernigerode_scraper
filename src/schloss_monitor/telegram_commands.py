from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import quote, urlencode

from .notifiers.telegram import PostTransport, _default_post_transport, _telegram_response


class TelegramCommandKind(StrEnum):
    SCAN = "scan"
    LIST = "list"
    HELP = "help"


@dataclass(frozen=True)
class TelegramCommand:
    kind: TelegramCommandKind
    chat_id: str
    update_id: int


@dataclass(frozen=True)
class TelegramCommandClient:
    bot_token: str
    chat_id: str
    post_transport: PostTransport = _default_post_transport

    def register_commands(self) -> None:
        self._post(
            "setMyCommands",
            {
                "commands": json.dumps(
                    [
                        {"command": "scan", "description": "Sofortigen Scan starten"},
                        {"command": "list", "description": "Gespeicherte freie Termine anzeigen"},
                        {"command": "help", "description": "Hilfe und Befehle anzeigen"},
                    ]
                )
            },
        )

    def send_help(self, chat_id: str) -> None:
        self._post(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": "Verfügbare Befehle:\n/scan – sofortigen Scan starten\n/list – gespeicherte freie Termine anzeigen\n/help – diese Hilfe anzeigen",
                "reply_markup": json.dumps(
                    {
                        "keyboard": [[{"text": "/scan"}, {"text": "/list"}], [{"text": "/help"}]],
                        "resize_keyboard": True,
                        "is_persistent": True,
                    }
                ),
            },
        )

    def parse_updates(self, updates: Sequence[object]) -> list[TelegramCommand]:
        commands: list[TelegramCommand] = []
        for update in updates:
            if not isinstance(update, Mapping):
                continue
            update_id = update.get("update_id")
            message = update.get("message")
            if not isinstance(update_id, int) or not isinstance(message, Mapping):
                continue
            chat = message.get("chat")
            text = message.get("text")
            if not isinstance(chat, Mapping) or not isinstance(text, str):
                continue
            chat_id = str(chat.get("id", ""))
            if chat_id != self.chat_id:
                continue
            command_name = text.strip().split(maxsplit=1)[0].split("@", 1)[0].lstrip("/").lower()
            try:
                kind = TelegramCommandKind(command_name)
            except ValueError:
                continue
            commands.append(TelegramCommand(kind=kind, chat_id=chat_id, update_id=update_id))
        return commands

    def _post(self, operation: str, values: Mapping[str, str]) -> None:
        url = f"https://api.telegram.org/bot{quote(self.bot_token, safe='')}/{operation}"
        _telegram_response(self.post_transport(url, urlencode(values).encode()), operation)
