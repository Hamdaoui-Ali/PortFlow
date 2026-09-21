"""Versioned, bounded manifests for the PF-107 offline handoff bundle."""

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast

import jsonschema  # type: ignore[import-untyped]

from .paths import ArtifactPathError, resolve_artifact_path

NOTEBOOK_FILE = "portflow_delta_lab.py"
SCHEMA_FILE = "schema.json"
RESULT_FILE = "expected-result.json"
FINGERPRINT_FILE = "input-fingerprint.json"
MANIFEST_FILE = "manifest.json"
TABLES = ("telemetry_events", "container_movements", "incidents", "alarms")
REASON_CODES = (
    "run_failed",
    "notebook_hash_mismatch",
    "schema_hash_mismatch",
    "fixture_hash_mismatch",
    "result_hash_mismatch",
    "artifact_path_invalid",
    "notebook_contract_invalid",
    "manifest_invalid",
)


class ManifestVerificationError(ValueError):
    """A bounded failure of the PF-107 artifact contract."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def _object_schema(properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
_COMMON = {
    "schema_version": {"type": "integer", "const": 1},
    "task": {"const": "PF-107"},
    "target": {"const": "databricks_free_edition"},
    "execution_mode": {"const": "offline_handoff"},
    "cloud_execution": {"const": "not_run"},
    "compute": {"const": "serverless"},
    "storage": {"const": "unity_catalog_volume_and_delta_tables"},
}
_PATH = {"type": "string", "minLength": 1}
_COUNT = {"type": "integer", "minimum": 0}
_SUCCESS_SCHEMA: dict[str, object] = _object_schema(
    {
        **_COMMON,
        "notebook": _object_schema({"path": _PATH, "sha256": _HASH}),
        "schema": _object_schema({"path": _PATH, "sha256": _HASH}),
        "fixture": _object_schema(
            {
                "tables": {"type": "integer", "const": 4},
                "rows": _object_schema({table: _COUNT for table in TABLES}),
                "sha256": _HASH,
            }
        ),
        "expected_result": _object_schema(
            {
                "path": _PATH,
                "rows": _COUNT,
                "sha256": _HASH,
                "result_sha256": _HASH,
            }
        ),
        "verification": _object_schema(
            {
                "status": {"const": "ok"},
                "reason_code": {"type": "null"},
                "verifier_version": {"const": "1"},
            }
        ),
    }
)
_ERROR_SCHEMA: dict[str, object] = _object_schema(
    {
        **_COMMON,
        "verification": _object_schema(
            {
                "status": {"const": "error"},
                "reason_code": {"enum": list(REASON_CODES)},
                "verifier_version": {"const": "1"},
            }
        ),
    }
)
_SCHEMA: dict[str, object] = {"oneOf": [_SUCCESS_SCHEMA, _ERROR_SCHEMA]}


def _validate_document(document: object) -> dict[str, object]:
    if not isinstance(document, dict) or type(document.get("schema_version")) is not int:
        raise ManifestVerificationError("manifest_invalid")
    if document.get("cloud_execution") not in {None, "not_run"}:
        raise ManifestVerificationError("cloud_execution_not_offline")
    try:
        jsonschema.validate(document, _SCHEMA)
    except jsonschema.ValidationError:
        raise ManifestVerificationError("manifest_invalid") from None
    return cast(dict[str, object], document)


def _validate_relative_path(value: object, root: Path) -> None:
    if not isinstance(value, str):
        raise ManifestVerificationError("artifact_path_invalid")
    windows = PureWindowsPath(value)
    if (
        not value
        or value == "."
        or windows.drive
        or windows.root
        or PurePosixPath(value).is_absolute()
        or ".." in windows.parts
        or ".." in PurePosixPath(value).parts
        or "\\" in value
        or ":" in value
    ):
        raise ManifestVerificationError("artifact_path_invalid")
    try:
        resolve_artifact_path(root, value)
    except ArtifactPathError:
        raise ManifestVerificationError("artifact_path_invalid") from None


def _validate_artifact_paths(document: Mapping[str, object], root: Path) -> None:
    for section in ("notebook", "schema", "expected_result"):
        if section in document:
            item = document[section]
            if not isinstance(item, dict):
                raise ManifestVerificationError("manifest_invalid")
            _validate_relative_path(item.get("path"), root)


def build_manifest(
    *,
    notebook_sha256: str,
    schema_sha256: str,
    fixture_rows: Mapping[str, int],
    fixture_sha256: str,
    expected_rows: int,
    expected_sha256: str,
    result_sha256: str,
) -> dict[str, object]:
    """Build and validate the successful version-1 PF-107 manifest."""
    document: dict[str, object] = {
        "schema_version": 1,
        "task": "PF-107",
        "target": "databricks_free_edition",
        "execution_mode": "offline_handoff",
        "cloud_execution": "not_run",
        "compute": "serverless",
        "storage": "unity_catalog_volume_and_delta_tables",
        "notebook": {"path": NOTEBOOK_FILE, "sha256": notebook_sha256},
        "schema": {"path": SCHEMA_FILE, "sha256": schema_sha256},
        "fixture": {
            "tables": len(fixture_rows),
            "rows": dict(fixture_rows),
            "sha256": fixture_sha256,
        },
        "expected_result": {
            "path": RESULT_FILE,
            "rows": expected_rows,
            "sha256": expected_sha256,
            "result_sha256": result_sha256,
        },
        "verification": {"status": "ok", "reason_code": None, "verifier_version": "1"},
    }
    return _validate_document(document)


def build_error_manifest(reason_code: str) -> dict[str, object]:
    """Build a failure manifest containing only a stable reason code."""
    document: dict[str, object] = {
        "schema_version": 1,
        "task": "PF-107",
        "target": "databricks_free_edition",
        "execution_mode": "offline_handoff",
        "cloud_execution": "not_run",
        "compute": "serverless",
        "storage": "unity_catalog_volume_and_delta_tables",
        "verification": {
            "status": "error",
            "reason_code": reason_code,
            "verifier_version": "1",
        },
    }
    return _validate_document(document)


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of exact file bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_text(path: Path, content: str) -> None:
    """Write UTF-8 text with stable LF bytes below the supplied root."""
    target = resolve_artifact_path(path.parent, path.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        handle.write(content)


def write_json(path: Path, value: object) -> None:
    """Write sorted, indented JSON with one terminating newline."""
    write_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_manifest(path: Path, manifest: Mapping[str, object]) -> None:
    """Validate and serialize a manifest without leaking runtime details."""
    document = _validate_document(dict(manifest))
    _validate_artifact_paths(document, path.parent)
    write_json(path, document)


def validate_manifest(path: Path, *, artifact_root: Path) -> dict[str, object]:
    """Load and validate a manifest while enforcing declared path containment."""
    try:
        relative = path.absolute().relative_to(artifact_root.absolute()).as_posix()
        target = resolve_artifact_path(artifact_root, relative)
        document = json.loads(target.read_text(encoding="utf-8"))
    except ArtifactPathError:
        raise ManifestVerificationError("artifact_path_invalid") from None
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ManifestVerificationError("manifest_invalid") from None
    validated = _validate_document(document)
    _validate_artifact_paths(validated, artifact_root)
    return validated
