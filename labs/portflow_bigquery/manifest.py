"""Versioned, deterministic manifests for the offline portability bundle."""

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast

import jsonschema  # type: ignore[import-untyped]

from .fixture import FixtureMetadata
from .paths import ArtifactPathError, resolve_artifact_path
from .reference import ReferenceResult

DRY_RUN_COMMAND = (
    "bq query --use_legacy_sql=false --dry_run --project_id=demo-project "
    "< .portability/bigquery/overview_kpis.sql"
)


class ManifestVerificationError(ValueError):
    """A bounded failure of the offline bundle contract."""

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


_COMMON: dict[str, object] = {
    "schema_version": {"type": "integer", "const": 1},
    "task": {"const": "PF-106"},
    "dialect": {"const": "bigquery_google_sql"},
    "execution_mode": {"const": "offline"},
    "cloud_execution": {"const": "not_run"},
}
_HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
_TABLES = ("telemetry_events", "container_movements", "incidents", "alarms")


def _count_schema() -> dict[str, object]:
    return {"type": "integer", "minimum": 0}


_SCHEMA = {
    "oneOf": [
        _object_schema(
            {
                **_COMMON,
                "query": _object_schema(
                    {
                        "path": {"type": "string", "minLength": 1},
                        "sha256": _HASH,
                        "parser": {"const": "bigquery"},
                        "dry_run_command": {"const": DRY_RUN_COMMAND},
                    }
                ),
                "schema": _object_schema(
                    {
                        "path": {"type": "string", "minLength": 1},
                        "sha256": _HASH,
                    }
                ),
                "fixture": _object_schema(
                    {
                        "generator_version": {"const": "1"},
                        "tables": {"type": "integer", "const": 4},
                        "rows": _object_schema(
                            {table: _count_schema() for table in _TABLES}
                        ),
                        "sha256": _HASH,
                    }
                ),
                "reference": _object_schema(
                    {
                        "engine": {"const": "duckdb_dbt"},
                        "result_rows": _count_schema(),
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
        ),
        _object_schema(
            {
                **_COMMON,
                "verification": _object_schema(
                    {
                        "status": {"const": "error"},
                        "reason_code": {"enum": ["run_failed"]},
                        "verifier_version": {"const": "1"},
                    }
                ),
            }
        ),
    ],
}


def _validate(manifest: object) -> dict[str, object]:
    if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int:
        raise ManifestVerificationError("manifest_invalid")
    if "cloud_execution" in manifest and manifest["cloud_execution"] != "not_run":
        raise ManifestVerificationError("cloud_execution_not_offline")
    try:
        jsonschema.validate(manifest, _SCHEMA)
    except jsonschema.ValidationError:
        raise ManifestVerificationError("manifest_invalid") from None
    return cast(dict[str, object], manifest)


def build_manifest(
    *,
    query_sha256: str,
    schema_sha256: str,
    fixture: FixtureMetadata,
    reference: ReferenceResult,
    dry_run_command: str,
) -> dict[str, object]:
    """Build the successful version-1 manifest using relative artifact names."""
    manifest = _common_manifest()
    manifest.update(
        {
            "query": {
                "path": "overview_kpis.sql",
                "sha256": query_sha256,
                "parser": "bigquery",
                "dry_run_command": dry_run_command,
            },
            "schema": {"path": "schema.json", "sha256": schema_sha256},
            "fixture": {
                "generator_version": fixture.generator_version,
                "tables": len(fixture.rows_by_table),
                "rows": dict(fixture.rows_by_table),
                "sha256": fixture.logical_sha256,
            },
            "reference": {
                "engine": "duckdb_dbt",
                "result_rows": len(reference.rows),
                "result_sha256": reference.result_sha256,
            },
            "verification": {"status": "ok", "reason_code": None, "verifier_version": "1"},
        }
    )
    return _validate(manifest)


def _common_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "task": "PF-106",
        "dialect": "bigquery_google_sql",
        "execution_mode": "offline",
        "cloud_execution": "not_run",
    }


def build_error_manifest(reason_code: str) -> dict[str, object]:
    """Build a bounded failure manifest, without exception text or artifacts."""
    manifest = _common_manifest()
    manifest["verification"] = {
        "status": "error",
        "reason_code": reason_code,
        "verifier_version": "1",
    }
    return _validate(manifest)


def file_sha256(path: Path) -> str:
    """Hash exact file bytes (in particular, the copied schema)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_text(path: Path, content: str) -> None:
    """Write UTF-8 without platform newline translation or following links."""
    target = resolve_artifact_path(path.parent, path.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="")


def write_json(path: Path, value: object) -> None:
    """Write sorted, indented JSON and exactly one terminating newline."""
    write_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_manifest(path: Path, manifest: Mapping[str, object]) -> None:
    """Validate a manifest before serializing it."""
    validated = _validate(dict(manifest))
    _validate_artifact_paths(validated, path.parent)
    write_json(path, validated)


def _validate_artifact_paths(manifest: Mapping[str, object], root: Path) -> None:
    for section in ("query", "schema"):
        if section not in manifest:
            continue
        value = cast(dict[str, object], manifest[section])["path"]
        relative = cast(str, value)
        # Reject Windows drives and traversal even on POSIX hosts, including
        # absolute paths that happen to point back inside the artifact root.
        windows = PureWindowsPath(relative)
        if (
            windows.drive
            or windows.root
            or PurePosixPath(relative).is_absolute()
            or ".." in windows.parts
            or "\\" in relative
            or ":" in relative
            or relative == "."
        ):
            raise ManifestVerificationError("artifact_path_invalid")
        try:
            resolve_artifact_path(root, relative)
        except ArtifactPathError:
            raise ManifestVerificationError("artifact_path_invalid") from None


def validate_manifest(path: Path, *, artifact_root: Path) -> dict[str, object]:
    """Validate either manifest form and guard all declared artifact paths."""
    try:
        # Do not resolve away a link before the path helper can inspect it.
        relative = path.absolute().relative_to(artifact_root.absolute()).as_posix()
        target = resolve_artifact_path(artifact_root, relative)
    except ValueError:
        raise ManifestVerificationError("artifact_path_invalid") from None
    try:
        manifest = _validate(json.loads(target.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ManifestVerificationError("manifest_invalid") from None
    _validate_artifact_paths(manifest, artifact_root)
    return manifest
