from datetime import UTC, datetime, timedelta
from pathlib import Path

from benchmarks.portflow_benchmarks.engines import run_duckdb, run_polars
from benchmarks.portflow_benchmarks.fixture import generate_fixture
from benchmarks.portflow_benchmarks.models import FixtureSpec, WorkloadSpec


def test_shared_workload_smoke_matches_across_host_engines(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixture"
    generate_fixture(FixtureSpec(seed=7, rows=1_000), fixture_dir)
    workload = WorkloadSpec(
        window_start=datetime(2026, 1, 1, tzinfo=UTC),
        window_end=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=12),
    )

    duckdb_result = run_duckdb(fixture_dir, workload)
    polars_result = run_polars(fixture_dir, workload)

    assert duckdb_result.result_sha256 == polars_result.result_sha256
    assert duckdb_result.result_rows == polars_result.result_rows
