from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[2]


def test_streaming_runbook_documents_pf104_start_inspect_and_cleanup() -> None:
    runbook = (REPOSITORY_ROOT / "docs" / "runbooks" / "local-streaming.md").read_text(
        encoding="utf-8"
    )

    for required in (
        "PF-104",
        "docker compose --profile streaming --profile observability up -d --wait",
        "http://127.0.0.1:9108/metrics",
        "http://127.0.0.1:9090",
        "http://127.0.0.1:3000",
        "PORTFLOW_GRAFANA_ADMIN_PASSWORD",
        "read-only",
        "stream_runs",
        "docker compose --profile observability down -v portflow-metrics prometheus grafana",
    ):
        assert required in runbook


def test_public_docs_keep_observability_local_only() -> None:
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (REPOSITORY_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "PF-104" in readme
    assert "Prometheus" in readme
    assert "Grafana" in readme
    assert "PF-104" in changelog
    assert "local" in changelog.lower()
