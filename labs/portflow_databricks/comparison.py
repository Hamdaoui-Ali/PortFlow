"""Deterministic PF-108 reports for manually supplied cloud results."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast

import jsonschema  # type: ignore[import-untyped]

from labs.portflow_bigquery.canonical import canonicalize_rows

from .paths import ArtifactPathError, resolve_comparison_path

REPORT_FILE = "comparison.json"
CLOUD_RESULT_FILE = "cloud-result.json"
REASON_CODES = (
    "artifact_path_invalid",
    "handoff_invalid",
    "cloud_result_invalid",
    "result_hash_mismatch",
    "cloud_result_hash_mismatch",
    "comparison_invalid",
)


class ComparisonVerificationError(ValueError):
    """A bounded failure of the PF-108 comparison contract."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class ComparisonSpec:
    """Paths needed to compare one supplied Gold result."""

    repository_root: Path
    handoff_manifest: Path
    cloud_result: Path
    output_path: Path


def _object_schema(properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
_COUNT = {"type": "integer", "minimum": 0}
_SCHEMA: dict[str, object] = _object_schema(
    {
        "schema_version": {"type": "integer", "const": 1},
        "task": {"const": "PF-108"},
        "target": {"const": "databricks_free_edition"},
        "execution_mode": {"const": "manual_result_comparison"},
        "cloud_execution": {"const": "result_supplied"},
        "reference": _object_schema(
            {
                "task": {"const": "PF-107"},
                "manifest_sha256": _HASH,
                "result_rows": _COUNT,
                "result_sha256": _HASH,
            }
        ),
        "cloud_result": _object_schema(
            {
                "path": {"type": "string", "minLength": 1},
                "sha256": _HASH,
                "result_rows": _COUNT,
                "result_sha256": _HASH,
            }
        ),
        "comparison": _object_schema(
            {
                "status": {"enum": ["match", "mismatch"]},
                "reason_code": {"enum": [None, "result_hash_mismatch"]},
                "verifier_version": {"const": "1"},
            }
        ),
    }
)


def _validate_document(document: object) -> dict[str, object]:
    try:
        jsonschema.validate(document, _SCHEMA)
    except jsonschema.ValidationError:
        raise ComparisonVerificationError("comparison_invalid") from None
    return cast(dict[str, object], document)


def _validate_relative_path(value: object, artifact_root: Path) -> str:
    if not isinstance(value, str):
        raise ComparisonVerificationError("artifact_path_invalid")
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value)
    if (
        not value
        or value == "."
        or windows.drive
        or windows.root
        or posix.is_absolute()
        or ".." in windows.parts
        or ".." in posix.parts
        or "\\" in value
        or ":" in value
    ):
        raise ComparisonVerificationError("artifact_path_invalid")
    try:
        resolve_comparison_path(artifact_root, value)
    except ArtifactPathError:
        raise ComparisonVerificationError("artifact_path_invalid") from None
    return value


def _validate_report_paths(document: Mapping[str, object], artifact_root: Path) -> None:
    cloud_result = document.get("cloud_result")
    if not isinstance(cloud_result, dict):
        raise ComparisonVerificationError("comparison_invalid")
    _validate_relative_path(cloud_result.get("path"), artifact_root)


def build_comparison_report(
    *,
    reference_manifest_sha256: str,
    reference_rows: int,
    reference_result_sha256: str,
    cloud_result_path: str,
    cloud_file_sha256: str,
    cloud_rows: int,
    cloud_result_sha256: str,
) -> dict[str, object]:
    """Build the deterministic report for a match or semantic mismatch."""
    matched = reference_rows == cloud_rows and reference_result_sha256 == cloud_result_sha256
    document: dict[str, object] = {
        "schema_version": 1,
        "task": "PF-108",
        "target": "databricks_free_edition",
        "execution_mode": "manual_result_comparison",
        "cloud_execution": "result_supplied",
        "reference": {
            "task": "PF-107",
            "manifest_sha256": reference_manifest_sha256,
            "result_rows": reference_rows,
            "result_sha256": reference_result_sha256,
        },
        "cloud_result": {
            "path": cloud_result_path,
            "sha256": cloud_file_sha256,
            "result_rows": cloud_rows,
            "result_sha256": cloud_result_sha256,
        },
        "comparison": {
            "status": "match" if matched else "mismatch",
            "reason_code": None if matched else "result_hash_mismatch",
            "verifier_version": "1",
        },
    }
    return _validate_document(document)


def build_mismatch_report(
    *,
    reference_manifest_sha256: str,
    reference_rows: int,
    reference_result_sha256: str,
    cloud_result_path: str,
    cloud_file_sha256: str,
    cloud_rows: int,
    cloud_result_sha256: str,
) -> dict[str, object]:
    """Build a valid report that records a canonical result mismatch."""
    if reference_rows == cloud_rows and reference_result_sha256 == cloud_result_sha256:
        raise ComparisonVerificationError("comparison_invalid")
    return build_comparison_report(
        reference_manifest_sha256=reference_manifest_sha256,
        reference_rows=reference_rows,
        reference_result_sha256=reference_result_sha256,
        cloud_result_path=cloud_result_path,
        cloud_file_sha256=cloud_file_sha256,
        cloud_rows=cloud_rows,
        cloud_result_sha256=cloud_result_sha256,
    )


def load_result_rows(path: Path) -> list[dict[str, object]]:
    """Load and validate the JSON row list used by the shared KPI contract."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError
        rows: list[dict[str, object]] = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError
            row = dict(item)
            for field in ("source_period_start", "source_period_end"):
                value = row.get(field)
                if not isinstance(value, str) or not value.endswith("Z"):
                    raise ValueError
                row[field] = datetime.fromisoformat(value[:-1] + "+00:00")
            rows.append(row)
        canonicalize_rows(rows)
        return rows
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, OverflowError):
        raise ComparisonVerificationError("cloud_result_invalid") from None


def _target_path(path: Path, artifact_root: Path) -> Path:
    try:
        relative = path.absolute().relative_to(artifact_root.absolute()).as_posix()
    except ValueError:
        raise ComparisonVerificationError("artifact_path_invalid") from None
    try:
        return resolve_comparison_path(artifact_root, relative)
    except ArtifactPathError:
        raise ComparisonVerificationError("artifact_path_invalid") from None


def write_comparison_report(
    path: Path,
    report: Mapping[str, object],
    *,
    artifact_root: Path,
) -> None:
    """Validate and serialize a report below the PF-108 artifact root."""
    document = _validate_document(dict(report))
    _validate_report_paths(document, artifact_root)
    target = _target_path(path, artifact_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
