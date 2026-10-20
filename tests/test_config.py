from __future__ import annotations

from pathlib import Path

import pytest

from schloss_monitor.config import ConfigError, load_settings


def write_config(path: Path, interval_seconds: int = 3600) -> None:
    path.write_text(
        f"""
[monitor]
interval_seconds = {interval_seconds}
run_immediately = true
timezone = "Europe/Berlin"

[scraper]
url = "https://www.schloss-wernigerode.de/kalender/die-schule-der-magischen-tiere#termine"
headless = true
navigation_timeout_ms = 30000
max_load_more_clicks = 100
request_delay_seconds = 1.5

[storage]
db_path = "data/appointments.sqlite3"

[logging]
level = "INFO"

[telegram]
enabled = false
""".strip()
        ,
        encoding="utf-8",
    )


def test_environment_overrides_toml_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "config.toml"
    write_config(config_file)
    monkeypatch.setenv("MONITOR_INTERVAL_SECONDS", "90")
    monkeypatch.setenv("MONITOR_DB_PATH", "custom.sqlite3")
    monkeypatch.setenv("MONITOR_HEADLESS", "false")
    monkeypatch.setenv("MONITOR_LOG_LEVEL", "debug")
    monkeypatch.setenv("MONITOR_REQUEST_DELAY_SECONDS", "2.25")
    monkeypatch.setenv("MONITOR_TELEGRAM_ENABLED", "true")

    settings = load_settings(config_file)

    assert settings.monitor.interval_seconds == 90
    assert settings.storage.db_path == Path("custom.sqlite3")
    assert settings.scraper.headless is False
    assert settings.logging.level == "DEBUG"
    assert settings.scraper.request_delay_seconds == 2.25
    assert settings.telegram.enabled is True


def test_invalid_interval_is_rejected(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    write_config(config_file, interval_seconds=0)

    with pytest.raises(ConfigError, match="interval_seconds"):
        load_settings(config_file)
