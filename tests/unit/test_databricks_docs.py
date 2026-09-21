from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_databricks_runbook_documents_bounded_offline_handoff() -> None:
    runbook = (ROOT / "docs/runbooks/databricks-free-edition.md").read_text(encoding="utf-8")
    for token in (
        "python -m labs.portflow_databricks run",
        "python -m labs.portflow_databricks verify",
        "cloud_execution",
        "offline_handoff",
        "Serverless",
        "Unity Catalog",
        "credentials",
        "Cleanup",
    ):
        assert token in runbook


def test_repository_navigation_mentions_pf107() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "databricks-free-edition.md" in readme
    assert "PF-107" in changelog
    assert ".databricks/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
