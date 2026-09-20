"""Benchmark profile orchestration."""

import platform
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from .engines import execute_workload
from .fixture import generate_fixture
from .models import EngineExecution, FixtureSpec, WorkloadSpec
from .report import write_report
from .spark_runner import SPARK_ROOT, failure_execution, run_pyspark
from .timing import DEFAULT_REPETITIONS, DEFAULT_WARMUPS, summarize_timings

PROFILES = {
    "smoke": 10_000,
    "small": 100_000,
    "medium": 1_000_000,
    "large": 5_000_000,
}
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPOSITORY_ROOT / ".benchmarks" / "fixtures"
REPORT_ROOT = REPOSITORY_ROOT / ".benchmarks" / "reports"
WORKLOAD_NAME = "telemetry_terminal_state_summary"
FIXTURE_START = datetime(2026, 1, 1, tzinfo=UTC)


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else "unknown"


def _engine_report(
    execution: EngineExecution,
    *,
    timed_seconds: list[float] | None = None,
    warmup_seconds: float | None = None,
    input_rows: int | None = None,
) -> dict[str, object]:
    samples = list(execution.timed_seconds if timed_seconds is None else timed_seconds)
    if execution.status != "ok":
        return {
            "name": execution.name,
            "version": execution.version,
            "startup_seconds": execution.startup_seconds,
            "warmup_seconds": execution.warmup_seconds,
            "timed_seconds": samples,
            "median_seconds": 0.0,
            "p95_seconds": 0.0,
            "rows_per_second": 0.0,
            "result_sha256": execution.result_sha256,
            "result_rows": len(execution.result_rows),
            "status": execution.status,
            "reason_code": execution.reason_code,
        }
    summary = summarize_timings(samples)
    return {
        "name": execution.name,
        "version": execution.version,
        "startup_seconds": execution.startup_seconds,
        "warmup_seconds": execution.warmup_seconds
        if warmup_seconds is None
        else warmup_seconds,
        "timed_seconds": samples,
        "median_seconds": summary.median_seconds,
        "p95_seconds": summary.p95_seconds,
        "rows_per_second": (
            input_rows if input_rows is not None else len(execution.result_rows)
        )
        / summary.median_seconds
        if summary.median_seconds > 0
        else 0.0,
        "result_sha256": execution.result_sha256,
        "result_rows": len(execution.result_rows),
        "status": execution.status,
        "reason_code": execution.reason_code,
    }


def _run_host_engine(
    engine_name: str,
    fixture_dir: Path,
    workload: WorkloadSpec,
    warmups: int,
    repetitions: int,
    input_rows: int,
) -> dict[str, object]:
    warmup_seconds = 0.0
    for _ in range(warmups):
        warmup = execute_workload(engine_name, fixture_dir, workload)
        warmup_seconds += sum(warmup.timed_seconds)
    timed: list[float] = []
    last: EngineExecution | None = None
    for _ in range(repetitions):
        last = execute_workload(engine_name, fixture_dir, workload)
        timed.extend(last.timed_seconds)
    if last is None:
        return _engine_report(failure_execution("no_timed_samples"))
    return _engine_report(
        last,
        timed_seconds=timed,
        warmup_seconds=warmup_seconds,
        input_rows=input_rows,
    )


def _run_engine(
    engine_name: str,
    fixture_dir: Path,
    workload: WorkloadSpec,
    warmups: int,
    repetitions: int,
    input_rows: int,
) -> dict[str, object]:
    try:
        if engine_name == "pyspark":
            if warmups != DEFAULT_WARMUPS or repetitions != DEFAULT_REPETITIONS:
                return _engine_report(failure_execution("spark_protocol_fixed"))
            return _engine_report(
                run_pyspark(fixture_dir, workload, SPARK_ROOT),
                input_rows=input_rows,
            )
        return _run_host_engine(
            engine_name,
            fixture_dir,
            workload,
            warmups,
            repetitions,
            input_rows,
        )
    except Exception:
        return _engine_report(failure_execution("engine_execution_failed"))


def _complete_engine_hashes(engines: list[dict[str, object]]) -> tuple[str, int]:
    successful = [engine for engine in engines if engine["status"] == "ok"]
    if not successful:
        return "", 0
    result_hash = cast(str, successful[0]["result_sha256"])
    result_rows = cast(int, successful[0]["result_rows"])
    for engine in successful[1:]:
        if engine["result_sha256"] != result_hash:
            engine["status"] = "error"
            engine["reason_code"] = "result_hash_mismatch"
            engine["result_sha256"] = ""
    return result_hash, result_rows


def run_benchmark(
    profile: str,
    engines: Sequence[str],
    warmups: int = DEFAULT_WARMUPS,
    repetitions: int = DEFAULT_REPETITIONS,
    report_path: Path | None = None,
) -> dict[str, object]:
    """Generate a profile fixture, run engines, and write a validated report."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile: {profile}")
    if warmups < 0 or repetitions <= 0:
        raise ValueError("warmups must be non-negative and repetitions must be positive")
    selected = [engine.strip() for engine in engines if engine.strip()]
    if not selected:
        raise ValueError("at least one engine is required")
    fixture_dir = FIXTURE_ROOT / profile
    metadata = generate_fixture(FixtureSpec(seed=42, rows=PROFILES[profile]), fixture_dir)
    workload = WorkloadSpec(
        window_start=FIXTURE_START,
        window_end=FIXTURE_START + timedelta(minutes=5 * metadata.rows),
    )
    engine_reports = [
        _run_engine(engine, fixture_dir, workload, warmups, repetitions, metadata.rows)
        for engine in selected
    ]
    result_hash, result_rows = _complete_engine_hashes(engine_reports)
    report: dict[str, object] = {
        "schema_version": 1,
        "fixture": {
            "seed": metadata.seed,
            "rows": metadata.rows,
            "logical_sha256": metadata.logical_sha256,
            "bytes": metadata.bytes,
            "generator_version": metadata.generator_version,
        },
        "workload": {
            "name": WORKLOAD_NAME,
            "window_start": workload.window_start.isoformat().replace("+00:00", "Z"),
            "window_end": workload.window_end.isoformat().replace("+00:00", "Z"),
            "result_rows": result_rows,
            "result_sha256": result_hash,
        },
        "environment": {
            "git_sha": _git_sha(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "engines": engine_reports,
    }
    write_report(report, report_path or REPORT_ROOT / "latest.json")
    return report


def verify_report(path: Path) -> None:
    """Validate a report and require every selected engine to have succeeded."""
    from .report import read_report, validate_report

    report = read_report(path)
    validate_report(report)
    engines = cast(list[dict[str, object]], report["engines"])
    if any(engine["status"] != "ok" for engine in engines):
        raise ValueError("report contains unavailable or failed engines")
