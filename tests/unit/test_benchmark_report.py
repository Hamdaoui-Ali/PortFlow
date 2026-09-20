import json
from pathlib import Path

import pytest
from benchmarks.portflow_benchmarks.report import validate_report, write_report

RESULT_HASH = "a" * 64


def valid_report() -> dict[str, object]:
    engines = []
    for name in ("duckdb", "polars", "pyspark"):
        engines.append(
            {
                "name": name,
                "version": "1.0",
                "startup_seconds": 0.1,
                "warmup_seconds": 0.2,
                "timed_seconds": [0.3, 0.4, 0.5],
                "median_seconds": 0.4,
                "p95_seconds": 0.5,
                "rows_per_second": 5.0,
                "result_sha256": RESULT_HASH,
                "result_rows": 2,
                "status": "ok",
                "reason_code": None,
            }
        )
    return {
        "schema_version": 1,
        "fixture": {
            "seed": 42,
            "rows": 1_000,
            "logical_sha256": RESULT_HASH,
            "bytes": 123,
            "generator_version": "1",
        },
        "workload": {
            "name": "telemetry_terminal_state_summary",
            "window_start": "2026-01-01T00:00:00Z",
            "window_end": "2026-01-04T11:20:00Z",
            "result_rows": 2,
            "result_sha256": RESULT_HASH,
        },
        "environment": {
            "git_sha": "b" * 12,
            "platform": "Windows",
            "python": "3.12.0",
        },
        "engines": engines,
    }


def test_valid_report_passes_and_serializes_without_payloads(tmp_path: Path) -> None:
    report = valid_report()
    validate_report(report)

    path = tmp_path / "report.json"
    write_report(report, path)
    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert loaded == report
    assert "rows" not in loaded["engines"][0]


def test_report_rejects_absolute_paths() -> None:
    report = valid_report()
    report["fixture"]["path"] = str(Path.cwd())

    with pytest.raises(ValueError, match="absolute path"):
        validate_report(report)


def test_report_rejects_unknown_engine() -> None:
    report = valid_report()
    report["engines"][0]["name"] = "oracle"

    with pytest.raises(ValueError, match="unknown engine"):
        validate_report(report)


def test_report_rejects_missing_hash() -> None:
    report = valid_report()
    del report["fixture"]["logical_sha256"]

    with pytest.raises(ValueError, match="logical_sha256"):
        validate_report(report)


def test_report_rejects_row_count_mismatch() -> None:
    report = valid_report()
    report["engines"][0]["result_rows"] = 3

    with pytest.raises(ValueError, match="result_rows"):
        validate_report(report)


def test_report_allows_unavailable_engine_without_result_rows() -> None:
    report = valid_report()
    unavailable = report["engines"][0]
    unavailable["status"] = "unavailable"
    unavailable["reason_code"] = "docker_unavailable"
    unavailable["result_sha256"] = ""
    unavailable["result_rows"] = 0

    validate_report(report)


def test_report_rejects_unbounded_failure_reason() -> None:
    report = valid_report()
    failed = report["engines"][0]
    failed["status"] = "unavailable"
    failed["reason_code"] = "x" * 65
    failed["result_sha256"] = ""

    with pytest.raises(ValueError, match="reason_code"):
        validate_report(report)


def test_report_rejects_malformed_timing_data() -> None:
    report = valid_report()
    report["engines"][0]["timed_seconds"] = []

    with pytest.raises(ValueError, match="timed_seconds"):
        validate_report(report)
