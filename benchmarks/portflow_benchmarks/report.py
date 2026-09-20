"""Versioned, bounded benchmark report validation and serialization."""

import json
import math
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from .paths import reject_reparse_components
from .timing import summarize_timings

REPORT_SCHEMA_VERSION = 1
ENGINE_NAMES = {"duckdb", "polars", "pyspark"}
REPORT_ROOT = Path(__file__).resolve().parents[2] / ".benchmarks" / "reports"
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REASON_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")
_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")


def _is_absolute_path(value: str) -> bool:
    return (
        os.path.isabs(value)
        or bool(_DRIVE_PATH_PATTERN.match(value))
        or value.startswith("\\\\")
    )


def _contains_absolute_path(value: object) -> bool:
    if isinstance(value, str):
        return _is_absolute_path(value)
    if isinstance(value, Mapping):
        return any(_contains_absolute_path(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_absolute_path(item) for item in value)
    return False


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return cast(dict[str, object], value)


def _hash(value: object, field: str, *, allow_empty: bool = False) -> str:
    if allow_empty and value == "":
        return ""
    if not isinstance(value, str) or not _HASH_PATTERN.fullmatch(value):
        raise ValueError(f"{field} must be a SHA-256 hash")
    return value


def _number(value: object, field: str, *, allow_zero: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or (not allow_zero and number <= 0) or number < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return number


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _resolve_report_path(path: Path, artifact_root: Path | None = None) -> Path:
    root_candidate = artifact_root or REPORT_ROOT
    reject_reparse_components(
        root_candidate,
        message="report root must not contain symbolic links or reparse points",
    )
    reject_reparse_components(
        path,
        message="report path must not contain symbolic links or reparse points",
    )
    root = root_candidate.resolve(strict=False)
    candidate = path.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("report path must remain within benchmark reports") from error
    return candidate


def _validate_fixture(fixture: Mapping[str, object]) -> None:
    _integer(fixture.get("seed"), "fixture.seed")
    _integer(fixture.get("rows"), "fixture.rows")
    _hash(fixture.get("logical_sha256"), "fixture.logical_sha256")
    _integer(fixture.get("bytes"), "fixture.bytes")
    if not isinstance(fixture.get("generator_version"), str):
        raise ValueError("fixture.generator_version must be a string")


def _validate_workload(workload: Mapping[str, object]) -> int:
    if workload.get("name") != "telemetry_terminal_state_summary":
        raise ValueError("invalid workload name")
    for field in ("window_start", "window_end"):
        value = workload.get(field)
        if not isinstance(value, str) or not value.endswith("Z"):
            raise ValueError(f"workload.{field} must be a UTC string")
    return _integer(workload.get("result_rows"), "workload.result_rows")


def _timing_samples(engine: Mapping[str, object], index: int, *, required: bool) -> list[float]:
    timed = engine.get("timed_seconds")
    if not isinstance(timed, list):
        raise ValueError(f"engines[{index}].timed_seconds must be a list")
    if required and not timed:
        raise ValueError(f"engines[{index}].timed_seconds must not be empty")
    return [float(value) for value in timed]


def _validate_successful_engine(
    engine: Mapping[str, object],
    index: int,
) -> str:
    samples = _timing_samples(engine, index, required=True)
    summary = summarize_timings(samples)
    median_seconds = _number(engine.get("median_seconds"), f"engines[{index}].median_seconds")
    if abs(median_seconds - summary.median_seconds) > 1e-9:
        raise ValueError(f"engines[{index}].median_seconds is invalid")
    p95_seconds = _number(engine.get("p95_seconds"), f"engines[{index}].p95_seconds")
    if abs(p95_seconds - summary.p95_seconds) > 1e-9:
        raise ValueError(f"engines[{index}].p95_seconds is invalid")
    result_hash = _hash(engine.get("result_sha256"), f"engines[{index}].result_sha256")
    if engine.get("reason_code") not in (None, ""):
        raise ValueError(f"engines[{index}].reason_code must be empty for ok status")
    return result_hash


def _validate_unavailable_engine(engine: Mapping[str, object], index: int) -> None:
    reason = engine.get("reason_code")
    if not isinstance(reason, str) or not _REASON_PATTERN.fullmatch(reason):
        raise ValueError(f"engines[{index}].reason_code is invalid")
    _hash(
        engine.get("result_sha256"),
        f"engines[{index}].result_sha256",
        allow_empty=True,
    )
    samples = _timing_samples(engine, index, required=False)
    if samples:
        summarize_timings(samples)


def _validate_engine(
    engine: Mapping[str, object],
    index: int,
    result_rows: int,
) -> str | None:
    if not isinstance(engine.get("version"), str) or not engine["version"]:
        raise ValueError(f"engines[{index}].version must be a string")
    status = engine.get("status")
    if not isinstance(status, str) or status not in {"ok", "unavailable", "error"}:
        raise ValueError(f"engines[{index}].status is invalid")
    engine_rows = _integer(engine.get("result_rows"), f"engines[{index}].result_rows")
    if status == "ok" and engine_rows != result_rows:
        raise ValueError(f"engines[{index}].result_rows does not match workload.result_rows")
    for field in ("startup_seconds", "warmup_seconds", "rows_per_second"):
        _number(engine.get(field), f"engines[{index}].{field}")
    if status == "ok":
        return _validate_successful_engine(engine, index)
    _validate_unavailable_engine(engine, index)
    return None


def _validate_engines(value: object, result_rows: int) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("engines must be a non-empty list")
    successful_hashes: list[str] = []
    seen_names: set[str] = set()
    for index, raw_engine in enumerate(value):
        engine = _mapping(raw_engine, f"engines[{index}]")
        name = engine.get("name")
        if not isinstance(name, str) or name not in ENGINE_NAMES:
            raise ValueError(f"unknown engine: {name}")
        if name in seen_names:
            raise ValueError(f"duplicate engine: {name}")
        seen_names.add(name)
        result_hash = _validate_engine(engine, index, result_rows)
        if result_hash is not None:
            successful_hashes.append(result_hash)
    return successful_hashes


def validate_report(report: Mapping[str, object]) -> None:
    """Validate the shareable benchmark report contract."""
    if _contains_absolute_path(report):
        raise ValueError("absolute path is not allowed in a report")
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise ValueError("invalid schema_version")
    _validate_fixture(_mapping(report.get("fixture"), "fixture"))
    workload = _mapping(report.get("workload"), "workload")
    result_rows = _validate_workload(workload)
    successful_hashes = _validate_engines(report.get("engines"), result_rows)
    workload_hash = _hash(
        workload.get("result_sha256"),
        "workload.result_sha256",
        allow_empty=not successful_hashes,
    )
    if successful_hashes and any(result_hash != workload_hash for result_hash in successful_hashes):
        raise ValueError("engine result hashes do not match workload.result_sha256")


def write_report(
    report: Mapping[str, object],
    path: Path,
    *,
    artifact_root: Path | None = None,
) -> None:
    """Validate and write a stable JSON report."""
    validate_report(report)
    target = _resolve_report_path(path, artifact_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def read_report(path: Path, *, artifact_root: Path | None = None) -> dict[str, object]:
    """Read a JSON report as an object."""
    target = _resolve_report_path(path, artifact_root)
    value: Any = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("report must be a JSON object")
    return cast(dict[str, object], value)
