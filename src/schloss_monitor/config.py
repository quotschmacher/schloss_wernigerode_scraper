from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class ConfigError(ValueError):
    """Raised when the monitor configuration is invalid."""


@dataclass(frozen=True)
class MonitorSettings:
    interval_seconds: int
    run_immediately: bool
    timezone: str


@dataclass(frozen=True)
class ScraperSettings:
    url: str
    headless: bool
    navigation_timeout_ms: int
    max_load_more_clicks: int
    request_delay_seconds: float


@dataclass(frozen=True)
class StorageSettings:
    db_path: Path


@dataclass(frozen=True)
class LoggingSettings:
    level: str


@dataclass(frozen=True)
class TelegramSettings:
    enabled: bool


@dataclass(frozen=True)
class Settings:
    monitor: MonitorSettings
    scraper: ScraperSettings
    storage: StorageSettings
    logging: LoggingSettings
    telegram: TelegramSettings


def _as_bool(value: object, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ConfigError(f"{name} must be a boolean")


def _as_int(value: object, name: str, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{name} must be an integer") from error
    if parsed < minimum:
        raise ConfigError(f"{name} must be at least {minimum}")
    return parsed


def _as_float(value: object, name: str, minimum: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{name} must be a number") from error
    if parsed < minimum:
        raise ConfigError(f"{name} must be at least {minimum}")
    return parsed


def _section(data: dict[str, object], name: str) -> dict[str, object]:
    section = data.get(name)
    if not isinstance(section, dict):
        raise ConfigError(f"missing [{name}] section")
    return section


def _value(section: dict[str, object], key: str, environment: str | None = None) -> object:
    if environment and environment in os.environ:
        return os.environ[environment]
    if key not in section:
        raise ConfigError(f"missing configuration value {key}")
    return section[key]


def load_settings(config_file: Path) -> Settings:
    try:
        with config_file.open("rb") as handle:
            raw = tomllib.load(handle)
    except OSError as error:
        raise ConfigError(f"cannot read config file {config_file}: {error}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"invalid TOML in {config_file}: {error}") from error

    monitor = _section(raw, "monitor")
    scraper = _section(raw, "scraper")
    storage = _section(raw, "storage")
    logging = _section(raw, "logging")
    telegram = _section(raw, "telegram")

    url = str(_value(scraper, "url"))
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ConfigError("scraper.url must be an absolute HTTP(S) URL")

    log_level = str(_value(logging, "level", "MONITOR_LOG_LEVEL")).upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigError("logging.level must be a valid log level")

    return Settings(
        monitor=MonitorSettings(
            interval_seconds=_as_int(
                _value(monitor, "interval_seconds", "MONITOR_INTERVAL_SECONDS"),
                "monitor.interval_seconds",
            ),
            run_immediately=_as_bool(_value(monitor, "run_immediately"), "monitor.run_immediately"),
            timezone=str(_value(monitor, "timezone")),
        ),
        scraper=ScraperSettings(
            url=url,
            headless=_as_bool(_value(scraper, "headless", "MONITOR_HEADLESS"), "scraper.headless"),
            navigation_timeout_ms=_as_int(
                _value(scraper, "navigation_timeout_ms"),
                "scraper.navigation_timeout_ms",
            ),
            max_load_more_clicks=_as_int(
                _value(scraper, "max_load_more_clicks"),
                "scraper.max_load_more_clicks",
            ),
            request_delay_seconds=_as_float(
                _value(scraper, "request_delay_seconds", "MONITOR_REQUEST_DELAY_SECONDS"),
                "scraper.request_delay_seconds",
            ),
        ),
        storage=StorageSettings(
            db_path=Path(str(_value(storage, "db_path", "MONITOR_DB_PATH"))),
        ),
        logging=LoggingSettings(level=log_level),
        telegram=TelegramSettings(
            enabled=_as_bool(
                _value(telegram, "enabled", "MONITOR_TELEGRAM_ENABLED"),
                "telegram.enabled",
            ),
        ),
    )
