from pathlib import Path


def test_ghcr_workflow_publishes_only_after_merged_pr_or_manual_dispatch() -> None:
    workflow = Path(".github/workflows/publish-image.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "pull_request:" in workflow
    assert "types: [closed]" in workflow
    assert "github.event.pull_request.merged == true" in workflow
    assert "github.event.pull_request.base.ref == 'main'" in workflow
    assert "  push:\n" not in workflow
    assert "packages: write" in workflow
    assert "ghcr.io" in workflow
    assert "target: production" in workflow
    assert "${{ github.sha }}" in workflow
    assert ":latest" in workflow
    assert "Set package visibility to public" not in workflow
    assert "actions/checkout@v6" in workflow
    assert "docker/setup-buildx-action@v4" in workflow
    assert "docker/login-action@v4" in workflow
    assert "docker/build-push-action@v7" in workflow
