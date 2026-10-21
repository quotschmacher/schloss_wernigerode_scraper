from pathlib import Path


def test_ghcr_workflow_publishes_latest_and_commit_sha_from_main() -> None:
    workflow = Path(".github/workflows/publish-image.yml").read_text(encoding="utf-8")

    assert "branches: [main]" in workflow
    assert "packages: write" in workflow
    assert "ghcr.io" in workflow
    assert "target: production" in workflow
    assert "${{ github.sha }}" in workflow
    assert ":latest" in workflow
    assert "Set package visibility to public" not in workflow
