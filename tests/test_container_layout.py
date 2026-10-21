from pathlib import Path


def test_production_image_creates_runtime_configuration_from_tracked_template() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "COPY pyproject.toml README.md config.example.toml ./" in dockerfile
    assert "cp config.example.toml config.toml" in dockerfile


def test_monitor_and_dev_share_the_host_sqlite_directory() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert compose.count("- ./data:/data") == 2
