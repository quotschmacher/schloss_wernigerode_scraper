from pathlib import Path


def test_readme_contains_ghcr_deployment_compose_example() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "## Schnellstart mit GHCR" in readme
    assert "image: ghcr.io/quotschmacher/schloss_wernigerode_scraper:latest" in readme
    assert "env_file:" in readme
    assert "- .env" in readme
    assert "- ./data:/data" in readme
