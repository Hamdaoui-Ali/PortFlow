"""Host-side boundary for the isolated PySpark benchmark runner."""

import json
import os
import re
import shutil
import subprocess
from datetime import UTC
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from .canonical import canonicalize_rows, result_sha256
from .models import EngineExecution, WorkloadSpec

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPOSITORY_ROOT / ".benchmarks" / "fixtures"
SPARK_ROOT = REPOSITORY_ROOT / ".benchmarks" / "spark"
COMPOSE_FILE = "benchmarks/spark/compose.yaml"
SPARK_SERVICE = "pyspark"
RESULT_FILE = "result.json"
_REASON_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")


def _relative_under(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError as error:
        raise ValueError("paths must be within benchmark artifacts") from error


def validate_artifact_paths(fixture_dir: Path, output_dir: Path) -> None:
    """Ensure host paths cannot escape the benchmark artifact mounts."""
    _relative_under(fixture_dir, FIXTURE_ROOT)
    _relative_under(output_dir, SPARK_ROOT)


def _utc_text(value: object) -> str:
    return cast(str, cast(Any, value).astimezone(UTC).isoformat().replace("+00:00", "Z"))


def build_compose_command(
    fixture_dir: Path,
    workload: WorkloadSpec,
    output_dir: Path,
) -> tuple[list[str], dict[str, str]]:
    """Build the isolated Compose invocation and its bounded interpolation values."""
    validate_artifact_paths(fixture_dir, output_dir)
    fixture_subpath = _relative_under(fixture_dir, FIXTURE_ROOT)
    output_name = f"{_relative_under(output_dir, SPARK_ROOT)}/{RESULT_FILE}"
    environment = {
        "PF_BENCHMARK_FIXTURE_SUBPATH": fixture_subpath,
        "PF_BENCHMARK_WINDOW_START": _utc_text(workload.window_start),
        "PF_BENCHMARK_WINDOW_END": _utc_text(workload.window_end),
        "PF_BENCHMARK_OUTPUT_NAME": output_name,
        "PF_BENCHMARK_WARMUP": "1",
        "PF_BENCHMARK_REPETITIONS": "3",
    }
    return (
        [
            "docker",
            "compose",
            "-f",
            COMPOSE_FILE,
            "run",
            "--rm",
            SPARK_SERVICE,
        ],
        environment,
    )


def failure_execution(reason_code: str) -> EngineExecution:
    """Return safe unavailable metadata without exposing subprocess output."""
    safe_reason = reason_code if _REASON_PATTERN.fullmatch(reason_code) else "spark_failed"
    return EngineExecution(
        name="pyspark",
        version="unavailable",
        startup_seconds=0.0,
        warmup_seconds=0.0,
        timed_seconds=(),
        rows_per_second=0.0,
        result_sha256="",
        status="unavailable",
        reason_code=safe_reason,
    )


def _load_worker_result(path: Path) -> EngineExecution:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_rows = payload["result_rows"]
        rows = tuple(canonicalize_rows(cast(list[dict[str, object]], raw_rows)))
        timed_seconds = tuple(float(value) for value in payload["timed_seconds"])
        result_hash = result_sha256(rows)
        if result_hash != payload["result_sha256"]:
            return failure_execution("spark_result_hash_mismatch")
        if any(value < 0 for value in timed_seconds):
            return failure_execution("spark_result_invalid")
        return EngineExecution(
            name="pyspark",
            version=str(payload["version"]),
            startup_seconds=float(payload["startup_seconds"]),
            warmup_seconds=float(payload["warmup_seconds"]),
            timed_seconds=timed_seconds,
            rows_per_second=float(payload["rows_per_second"]),
            result_sha256=result_hash,
            result_rows=rows,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return failure_execution("spark_result_invalid")


def run_pyspark(
    fixture_dir: Path,
    workload: WorkloadSpec,
    output_dir: Path,
) -> EngineExecution:
    """Run PySpark in the pinned local container and read its bounded result."""
    validate_artifact_paths(fixture_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / RESULT_FILE
    if output_path.exists():
        output_path.unlink()
    if shutil.which("docker") is None:
        return failure_execution("docker_unavailable")
    command, overrides = build_compose_command(fixture_dir, workload, output_dir)
    environment = os.environ.copy()
    environment.update(overrides)
    started = perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=900,
        )
    except FileNotFoundError:
        return failure_execution("docker_unavailable")
    except subprocess.TimeoutExpired:
        return failure_execution("spark_timeout")
    if completed.returncode != 0:
        return failure_execution("spark_runner_failed")
    if not output_path.is_file():
        return failure_execution("spark_result_missing")
    execution = _load_worker_result(output_path)
    if execution.status != "ok":
        return execution
    return EngineExecution(
        name=execution.name,
        version=execution.version,
        startup_seconds=execution.startup_seconds or perf_counter() - started,
        warmup_seconds=execution.warmup_seconds,
        timed_seconds=execution.timed_seconds,
        rows_per_second=execution.rows_per_second,
        result_sha256=execution.result_sha256,
        status=execution.status,
        reason_code=execution.reason_code,
        result_rows=execution.result_rows,
    )
