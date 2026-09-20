from pathlib import Path

ROOT = Path(__file__).parents[2]
RUNBOOK = ROOT / "docs" / "runbooks" / "benchmarks.md"


def test_benchmark_artifacts_are_ignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert ".benchmarks/" in gitignore


def test_runbook_covers_profiles_and_engine_commands() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")

    for profile in ("smoke", "small", "medium", "large"):
        assert profile in runbook
    for command in (
        "python -m benchmarks.portflow_benchmarks run --profile smoke --engines duckdb,polars",
        "python -m benchmarks.portflow_benchmarks verify --report .benchmarks/reports/latest.json",
        (
            "python -m benchmarks.portflow_benchmarks "
            "run --profile medium --engines duckdb,polars,pyspark"
        ),
        "Remove-Item .benchmarks -Recurse -Force",
    ):
        assert command in runbook
    for engine in ("DuckDB", "Polars", "PySpark"):
        assert engine in runbook


def test_runbook_explains_reproducibility_and_boundaries() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8").lower()

    for phrase in (
        "docker",
        "sha256:",
        "deterministic",
        "logical hash",
        "host-specific timing",
        "unavailable",
        "verify",
        "not public data",
        "not committed",
    ):
        assert phrase in runbook


def test_readme_points_to_benchmark_runbook() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()

    assert "docs/runbooks/benchmarks.md" in readme
    assert "benchmark" in readme


def test_changelog_records_pf105() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").lower()

    assert "pf-105" in changelog
    assert "benchmark" in changelog
