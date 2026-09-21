import json
import math
from pathlib import Path

import pytest
from labs.portflow_bigquery.canonical import result_sha256
from labs.portflow_databricks.comparison import (
    ComparisonVerificationError,
    build_comparison_report,
    build_mismatch_report,
    load_result_rows,
)


def _row() -> dict[str, object]:
    return {
        "terminal_id": "TM-001",
        "source_period_start": "2026-09-02T00:00:00Z",
        "source_period_end": "2026-09-02T23:55:00Z",
        "available_intervals": 10,
        "scheduled_intervals": 10,
        "active_intervals": 8,
        "available_time_minutes": 600,
        "resolved_incident_count": 1,
        "repair_minutes": 12.5,
        "qualifying_failure_count": 1,
        "operating_hours": 10.0,
        "throughput": 4,
        "average_dwell_minutes": 42.125,
        "availability": 0.8,
        "utilization": 0.75,
        "mttr_minutes": 12.5,
        "mtbf_hours": 8.0,
        "active_incidents": 0,
        "critical_alarms": 1,
    }


def _write_result(path: Path, rows: list[dict[str, object]] | dict[str, object]) -> None:
    path.write_text(json.dumps(rows, allow_nan=True), encoding="utf-8")


def test_match_report_is_versioned_and_bounded() -> None:
    report = build_comparison_report(
        reference_manifest_path="handoff/manifest.json",
        reference_manifest_sha256="a" * 64,
        reference_rows=1,
        reference_result_sha256="b" * 64,
        cloud_result_path="cloud-result.json",
        cloud_file_sha256="c" * 64,
        cloud_rows=1,
        cloud_result_sha256="b" * 64,
    )

    assert report["task"] == "PF-108"
    assert report["execution_mode"] == "manual_result_comparison"
    assert report["cloud_execution"] == "result_supplied"
    assert report["comparison"] == {
        "status": "match",
        "reason_code": None,
        "verifier_version": "1",
    }


def test_load_result_rows_decodes_utc_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "cloud-result.json"
    _write_result(path, [_row()])

    loaded = load_result_rows(path)

    assert loaded[0]["source_period_start"].isoformat() == "2026-09-02T00:00:00+00:00"
    assert result_sha256(loaded) == result_sha256(
        [
            {
                **_row(),
                "source_period_start": loaded[0]["source_period_start"],
                "source_period_end": loaded[0]["source_period_end"],
            }
        ]
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: {"rows": value},
        lambda value: [{**value, "unexpected": 1}],
        lambda value: [value, value.copy()],
        lambda value: [{**value, "source_period_start": "2026-09-02T00:00:00"}],
        lambda value: [{**value, "availability": math.nan}],
    ],
)
def test_invalid_cloud_rows_have_one_bounded_reason(tmp_path: Path, mutate) -> None:
    path = tmp_path / "cloud-result.json"
    _write_result(path, mutate(_row()))

    with pytest.raises(ComparisonVerificationError, match="^cloud_result_invalid$"):
        load_result_rows(path)


def test_different_canonical_hashes_build_a_mismatch_report() -> None:
    report = build_mismatch_report(
        reference_manifest_path="handoff/manifest.json",
        reference_manifest_sha256="a" * 64,
        reference_rows=1,
        reference_result_sha256="b" * 64,
        cloud_result_path="cloud-result.json",
        cloud_file_sha256="c" * 64,
        cloud_rows=1,
        cloud_result_sha256="d" * 64,
    )

    assert report["comparison"] == {
        "status": "mismatch",
        "reason_code": "result_hash_mismatch",
        "verifier_version": "1",
    }
