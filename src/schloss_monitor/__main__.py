from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
from pathlib import Path

from .config import ConfigError, load_settings
from .monitor import PlaywrightScanner, run_forever, run_once
from .notifiers.console import ConsoleNotifier
from .notifiers.fanout import FanoutNotifier
from .notifiers.telegram import (
    TelegramApiError,
    TelegramNotifier,
    verify_bot_token,
    verify_chat_access,
)
from .storage import MonitorStorage, StorageError


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Schloss Wernigerode appointment monitor")
    parser.add_argument("--once", action="store_true", help="perform one complete scan and exit")
    parser.add_argument("--config", type=Path, help="path to config.toml")
    return parser.parse_args()


async def _run_until_shutdown(settings, storage: MonitorStorage, scanner: PlaywrightScanner, notifier) -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop_event.set)
    await run_forever(settings, storage, scanner, notifier, stop_event)


def main() -> int:
    args = _arguments()
    config_path = args.config or Path(os.environ.get("MONITOR_CONFIG_FILE", "config.toml"))
    try:
        settings = load_settings(config_path)
    except ConfigError as error:
        logging.basicConfig(level=logging.ERROR, format="%(asctime)s %(levelname)s %(message)s")
        logging.error("configuration error: %s", error)
        return 2
    logging.basicConfig(level=settings.logging.level, format="%(asctime)s %(levelname)s %(message)s")
    if settings.telegram.enabled:
        try:
            username = verify_bot_token(settings.telegram.bot_token or "")
            verify_chat_access(settings.telegram.bot_token or "", settings.telegram.chat_id or "")
        except TelegramApiError as error:
            logging.error("Telegram validation failed: %s", error)
            return 2
        logging.info("Telegram validation succeeded for @%s; recipient access verified", username)
    try:
        storage = MonitorStorage(settings.storage.db_path)
    except StorageError as error:
        logging.error("storage error: %s", error)
        return 2
    try:
        scanner = PlaywrightScanner(settings)
        console_notifier = ConsoleNotifier()
        notifier = FanoutNotifier(
            [
                console_notifier,
                TelegramNotifier(
                    enabled=settings.telegram.enabled,
                    bot_token=settings.telegram.bot_token,
                    chat_id=settings.telegram.chat_id,
                ),
            ]
        )
        if args.once:
            asyncio.run(run_once(settings, storage, scanner, notifier))
        else:
            asyncio.run(_run_until_shutdown(settings, storage, scanner, notifier))
    except KeyboardInterrupt:
        logging.info("shutdown requested")
    except Exception:
        logging.exception("monitor stopped after scan error")
        return 1
    finally:
        storage.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
