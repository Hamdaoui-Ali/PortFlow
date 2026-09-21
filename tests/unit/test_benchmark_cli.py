import json
from pathlib import Path

import pytest
from benchmarks.portflow_benchmarks import report as report_module
from benchmarks.portflow_benchmarks import runner
from benchmarks.portflow_benchmarks.cli import main
from benchmarks.portflow_benchmarks.models import EngineExecution, FixtureMetadata

from tests.unit.test_benchmark_report import valid_report


def test_cli_help_returns_success(capsys) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    assert "run" in capsys.readouterr().out


def test_cli_rejects_invalid_arguments() -> None:
    with pytest.raises(SystemExit) as error:
        main(["--unknown-option"])
    assert error.value.code == 2


def test_cli_verify_returns_success_for_valid_report(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    report_root = tmp_path / "reports"
    monkeypatch.setattr(report_module, "REPORT_ROOT", report_root)
    report_root.mkdir()
    report_path = report_root / "report.json"
    report_path.write_text(json.dumps(valid_report()), encoding="utf-8")

    assert main(["verify", "--report", str(report_path)]) == 0
    assert "verified" in capsys.readouterr().out.lower()


def test_cli_verify_returns_nonzero_for_invalid_report(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    report_root = tmp_path / "reports"
    monkeypatch.setattr(report_module, "REPORT_ROOT", report_root)
    report_root.mkdir()
    report_path = report_root / "report.json"
    report = valid_report()
    report["engines"][0]["result_sha256"] = "b" * 64
    report_path.write_text(json.dumps(report), encoding="utf-8")

    assert main(["verify", "--report", str(report_path)]) != 0
    assert "failed" in capsys.readouterr().out.lower()


def test_run_benchmark_uses_input_rows_for_throughput(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report_root = tmp_path / "reports"
    monkeypatch.setattr(report_module, "REPORT_ROOT", report_root)
    result_rows = (
        {
            "terminal_id": "TM-001",
            "state": "ACTIVE",
            "event_count": 2,
            "available_event_count": 2,
            "average_load_percent": 10.0,
            "average_temperature_c": 20.0,
        },
    )
    metadata = FixtureMetadata(
        seed=42,
        rows=1_000,
        generator_version="1",
        compression="zstd",
        fixture_dir=tmp_path,
        file_count=1,
        bytes=1,
        logical_sha256="c" * 64,
        schema=("event_id",),
    )
    execution = EngineExecution(
        name="duckdb",
        version="test",
        startup_seconds=0.1,
        warmup_seconds=0.0,
        timed_seconds=(0.5,),
        rows_per_second=0.0,
        result_sha256="a" * 64,
        result_rows=result_rows,
    )
    monkeypatch.setattr(runner, "generate_fixture", lambda spec, output: metadata)
    monkeypatch.setattr(
        runner,
        "execute_workload",
        lambda name, fixture, workload: execution,
    )

    report = runner.run_benchmark("smoke", ["duckdb"], report_path=report_root / "report.json")

    assert report["engines"][0]["rows_per_second"] == 2_000.0


def test_run_benchmark_preserves_engine_name_when_host_execution_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report_root = tmp_path / "reports"
    monkeypatch.setattr(report_module, "REPORT_ROOT", report_root)
    metadata = FixtureMetadata(
        seed=42,
        rows=1_000,
        generator_version="1",
        compression="zstd",
        fixture_dir=tmp_path,
        file_count=1,
        bytes=1,
        logical_sha256="c" * 64,
        schema=("event_id",),
    )
    monkeypatch.setattr(runner, "generate_fixture", lambda spec, output: metadata)

    def fail_execution(name, fixture, workload):
        raise RuntimeError("engine failed")

    monkeypatch.setattr(runner, "execute_workload", fail_execution)

    report = runner.run_benchmark("smoke", ["duckdb"], report_path=report_root / "report.json")

    assert report["engines"][0]["name"] == "duckdb"
    assert report["engines"][0]["status"] == "unavailable"
    assert report["engines"][0]["reason_code"] == "engine_execution_failed"
