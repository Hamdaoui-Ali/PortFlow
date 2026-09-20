from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_portability_artifacts_are_ignored() -> None:
    assert ".portability/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_runbook_contains_offline_commands_and_boundaries() -> None:
    runbook = (ROOT / "docs" / "runbooks" / "bigquery-portability.md").read_text(
        encoding="utf-8"
    ).lower()

    for phrase in (
        "python -m labs.portflow_bigquery run",
        "python -m labs.portflow_bigquery verify --manifest .portability/bigquery/manifest.json",
        "cloud_execution",
        "not_run",
        "countif",
        "timestamp_diff",
        "dry_run",
        "credentials",
        "not public data",
        "remove-item .portability -recurse -force",
    ):
        assert phrase in runbook


def test_readme_and_changelog_link_pf106_evidence() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").lower()

    assert "docs/runbooks/bigquery-portability.md" in readme
    assert "pf-106" in changelog
