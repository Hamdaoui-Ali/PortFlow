"""Deterministic PF-108 reports for manually supplied cloud results."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast

import jsonschema  # type: ignore[import-untyped]

from labs.portflow_bigquery.canonical import canonicalize_rows, result_sha256

from .manifest import file_sha256, validate_manifest
from .paths import (
    ArtifactPathError,
    resolve_artifact_path,
    resolve_artifact_root,
    resolve_comparison_path,
    resolve_comparison_root,
)
from .runner import verify_bundle

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
                "manifest_path": {"type": "string", "minLength": 1},
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
    validated = cast(dict[str, object], document)
    reference = cast(dict[str, object], validated["reference"])
    cloud_result = cast(dict[str, object], validated["cloud_result"])
    _validate_relative_name(reference["manifest_path"])
    _validate_relative_name(cloud_result["path"])
    return validated


def _validate_relative_name(value: object) -> str:
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
    return value


def _validate_relative_path(value: object, artifact_root: Path) -> str:
    value = _validate_relative_name(value)
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
    reference_manifest_path: str,
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
            "manifest_path": reference_manifest_path,
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
    reference_manifest_path: str,
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
        reference_manifest_path=reference_manifest_path,
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


def _repository_path(path: Path, repository_root: Path) -> Path:
    return path if path.is_absolute() else repository_root / path


def _resolve_handoff(
    manifest_path: Path,
    *,
    repository_root: Path,
) -> tuple[Path, Path, str]:
    try:
        handoff_root = resolve_artifact_root(repository_root=repository_root)
        absolute_manifest = _repository_path(manifest_path, repository_root)
        relative = absolute_manifest.absolute().relative_to(handoff_root.absolute()).as_posix()
        target = resolve_artifact_path(handoff_root, relative)
    except (ArtifactPathError, ValueError):
        raise ComparisonVerificationError("handoff_invalid") from None
    return handoff_root, target, relative


def compare_result(spec: ComparisonSpec) -> dict[str, object]:
    """Compare one supplied result with a verified PF-107 handoff."""
    try:
        comparison_root = resolve_comparison_root(repository_root=spec.repository_root)
        cloud_result = _target_path(
            _repository_path(spec.cloud_result, spec.repository_root), comparison_root
        )
        output_path = _target_path(
            _repository_path(spec.output_path, spec.repository_root), comparison_root
        )
    except ComparisonVerificationError:
        raise
    except (ArtifactPathError, OSError):
        raise ComparisonVerificationError("artifact_path_invalid") from None

    handoff_root, handoff_path, handoff_relative = _resolve_handoff(
        spec.handoff_manifest,
        repository_root=spec.repository_root,
    )
    try:
        verify_bundle(handoff_path, repository_root=spec.repository_root)
        handoff_manifest = validate_manifest(handoff_path, artifact_root=handoff_root)
        expected = cast(dict[str, object], handoff_manifest["expected_result"])
        reference_rows = cast(int, expected["rows"])
        reference_result_hash = cast(str, expected["result_sha256"])
        reference_manifest_hash = file_sha256(handoff_path)
    except (OSError, ValueError, TypeError, KeyError):
        raise ComparisonVerificationError("handoff_invalid") from None

    cloud_rows = load_result_rows(cloud_result)
    try:
        cloud_file_hash = file_sha256(cloud_result)
        cloud_result_hash = result_sha256(cloud_rows)
    except (OSError, ValueError, TypeError, OverflowError):
        raise ComparisonVerificationError("cloud_result_invalid") from None

    report = build_comparison_report(
        reference_manifest_path=handoff_relative,
        reference_manifest_sha256=reference_manifest_hash,
        reference_rows=reference_rows,
        reference_result_sha256=reference_result_hash,
        cloud_result_path=cloud_result.relative_to(comparison_root).as_posix(),
        cloud_file_sha256=cloud_file_hash,
        cloud_rows=len(cloud_rows),
        cloud_result_sha256=cloud_result_hash,
    )
    write_comparison_report(output_path, report, artifact_root=comparison_root)
    verify_comparison(output_path, repository_root=spec.repository_root)
    return report


def _comparison_report(path: Path, repository_root: Path) -> tuple[Path, Path, dict[str, object]]:
    try:
        root = resolve_comparison_root(repository_root=repository_root)
        target = _target_path(_repository_path(path, repository_root), root)
        document = json.loads(target.read_text(encoding="utf-8"))
        validated = _validate_document(document)
        _validate_report_paths(validated, root)
    except ComparisonVerificationError:
        raise
    except (ArtifactPathError, OSError, UnicodeError, json.JSONDecodeError, TypeError):
        raise ComparisonVerificationError("comparison_invalid") from None
    return root, target, validated


def verify_comparison(path: Path, *, repository_root: Path) -> None:
    """Verify a PF-108 report, its supplied result, and its PF-107 handoff."""
    comparison_root, _, report = _comparison_report(path, repository_root)
    reference = cast(dict[str, object], report["reference"])
    cloud = cast(dict[str, object], report["cloud_result"])
    try:
        handoff_root = resolve_artifact_root(repository_root=repository_root)
        manifest_relative = reference["manifest_path"]
        if not isinstance(manifest_relative, str):
            raise ValueError
        handoff_path = resolve_artifact_path(handoff_root, manifest_relative)
    except (ArtifactPathError, ValueError, TypeError):
        raise ComparisonVerificationError("comparison_invalid") from None

    try:
        verify_bundle(handoff_path, repository_root=repository_root)
    except (OSError, ValueError, TypeError, KeyError):
        raise ComparisonVerificationError("handoff_invalid") from None

    try:
        handoff_manifest = validate_manifest(handoff_path, artifact_root=handoff_root)
        expected = cast(dict[str, object], handoff_manifest["expected_result"])
        if (
            reference["task"] != "PF-107"
            or file_sha256(handoff_path) != reference["manifest_sha256"]
            or expected["rows"] != reference["result_rows"]
            or expected["result_sha256"] != reference["result_sha256"]
        ):
            raise ValueError
    except (OSError, ValueError, TypeError, KeyError):
        raise ComparisonVerificationError("comparison_invalid") from None

    try:
        cloud_relative = cloud["path"]
        if not isinstance(cloud_relative, str):
            raise ValueError
        cloud_path = resolve_comparison_path(comparison_root, cloud_relative)
        if file_sha256(cloud_path) != cloud["sha256"]:
            raise ValueError
        rows = load_result_rows(cloud_path)
        if len(rows) != cloud["result_rows"] or result_sha256(rows) != cloud["result_sha256"]:
            raise ValueError
    except ComparisonVerificationError:
        raise ComparisonVerificationError("cloud_result_hash_mismatch") from None
    except (ArtifactPathError, OSError, ValueError, TypeError, OverflowError):
        raise ComparisonVerificationError("cloud_result_hash_mismatch") from None


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
