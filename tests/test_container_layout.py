from pathlib import Path


def test_production_image_copies_runtime_configuration() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "COPY pyproject.toml README.md config.toml ./" in dockerfile


def test_monitor_and_dev_share_the_host_sqlite_directory() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert compose.count("- ./data:/data") == 2
