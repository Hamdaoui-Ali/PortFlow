from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from benchmarks.portflow_benchmarks.engines import (
    engine_version,
    execute_workload,
    run_duckdb,
    run_polars,
)
from benchmarks.portflow_benchmarks.fixture import generate_fixture
from benchmarks.portflow_benchmarks.models import FixtureSpec, WorkloadSpec
from benchmarks.portflow_benchmarks.workload import TELEMETRY_SUMMARY_WORKLOAD

RESULT_FIELDS = {
    "terminal_id",
    "state",
    "event_count",
    "available_event_count",
    "average_load_percent",
    "average_temperature_c",
}
START = datetime(2026, 1, 1, tzinfo=UTC)


def _fixture(tmp_path: Path) -> Path:
    fixture_dir = tmp_path / "fixture"
    generate_fixture(FixtureSpec(seed=42, rows=1_000), fixture_dir)
    return fixture_dir


def _full_window() -> WorkloadSpec:
    return WorkloadSpec(
        window_start=START,
        window_end=START + timedelta(minutes=5 * 1_000),
    )


def test_workload_contract_declares_shared_aggregation() -> None:
    assert "COUNT(*) AS event_count" in TELEMETRY_SUMMARY_WORKLOAD
    assert "GROUP BY terminal_id, state" in TELEMETRY_SUMMARY_WORKLOAD
    assert "event_timestamp >= ?" in TELEMETRY_SUMMARY_WORKLOAD
    assert "event_timestamp < ?" in TELEMETRY_SUMMARY_WORKLOAD


def test_duckdb_and_polars_return_equivalent_canonical_results(tmp_path: Path) -> None:
    fixture_dir = _fixture(tmp_path)
    workload = _full_window()

    duckdb_result = run_duckdb(fixture_dir, workload)
    polars_result = run_polars(fixture_dir, workload)

    assert duckdb_result.status == polars_result.status == "ok"
    assert duckdb_result.result_sha256 == polars_result.result_sha256
    assert duckdb_result.result_rows == polars_result.result_rows
    assert duckdb_result.result_rows
    assert all(set(row) == RESULT_FIELDS for row in duckdb_result.result_rows)
    assert all(isinstance(row["event_count"], int) for row in duckdb_result.result_rows)
    assert all(isinstance(row["available_event_count"], int) for row in duckdb_result.result_rows)
    assert all(
        round(row["average_load_percent"], 6) == row["average_load_percent"]
        for row in duckdb_result.result_rows
    )
    assert all(
        round(row["average_temperature_c"], 6) == row["average_temperature_c"]
        for row in duckdb_result.result_rows
    )
    assert list(duckdb_result.result_rows) == sorted(
        duckdb_result.result_rows,
        key=lambda row: (row["terminal_id"], row["state"]),
    )


def test_narrower_window_changes_the_canonical_result(tmp_path: Path) -> None:
    fixture_dir = _fixture(tmp_path)
    full_result = run_duckdb(fixture_dir, _full_window())
    narrow_result = run_duckdb(
        fixture_dir,
        WorkloadSpec(
            window_start=START,
            window_end=START + timedelta(minutes=5 * 100),
        ),
    )

    assert full_result.result_sha256 != narrow_result.result_sha256


def test_engine_dispatch_and_versions_are_explicit(tmp_path: Path) -> None:
    fixture_dir = _fixture(tmp_path)
    workload = _full_window()

    assert execute_workload("duckdb", fixture_dir, workload).status == "ok"
    assert execute_workload("polars", fixture_dir, workload).status == "ok"
    assert engine_version("duckdb")
    assert engine_version("polars")
    with pytest.raises(ValueError, match="unsupported engine"):
        execute_workload("spark", fixture_dir, workload)
    with pytest.raises(ValueError, match="unsupported engine"):
        engine_version("spark")
