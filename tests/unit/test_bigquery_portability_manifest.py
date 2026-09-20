import hashlib
import json
from pathlib import Path

import pytest
from labs.portflow_bigquery.fixture import FixtureMetadata
from labs.portflow_bigquery.manifest import (
    ManifestVerificationError,
    build_error_manifest,
    build_manifest,
    file_sha256,
    validate_manifest,
    write_json,
    write_manifest,
    write_text,
)
from labs.portflow_bigquery.reference import ReferenceResult
from labs.portflow_bigquery.runner import RunSpec, run_bundle, verify_bundle

COMMAND = (
    "bq query --use_legacy_sql=false --dry_run --project_id=demo-project "
    "< .portability/bigquery/overview_kpis.sql"
)


def success_manifest() -> dict:
    return build_manifest(
        query_sha256="a" * 64,
        schema_sha256="b" * 64,
        fixture=FixtureMetadata(
            seed=42,
            generator_version="1",
            rows_by_table={
                "telemetry_events": 4,
                "container_movements": 5,
                "incidents": 2,
                "alarms": 2,
            },
            logical_sha256="c" * 64,
            schema_sha256="b" * 64,
            schema={},
        ),
        reference=ReferenceResult(rows=({},), result_sha256="d" * 64),
        dry_run_command=COMMAND,
    )


def test_success_manifest_schema_and_deterministic_serialization(tmp_path: Path) -> None:
    manifest = success_manifest()
    path = tmp_path / "manifest.json"
    write_manifest(path, manifest)
    assert path.read_bytes() == (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    assert validate_manifest(path, artifact_root=tmp_path) == manifest
    assert manifest["query"] == {
        "path": "overview_kpis.sql",
        "sha256": "a" * 64,
        "parser": "bigquery",
        "dry_run_command": COMMAND,
    }
    assert manifest["schema"] == {"path": "schema.json", "sha256": "b" * 64}
    assert manifest["fixture"]["tables"] == 4
    assert manifest["reference"] == {
        "engine": "duckdb_dbt",
        "result_rows": 1,
        "result_sha256": "d" * 64,
    }


def test_error_form_is_bounded_and_cannot_verify_as_success(tmp_path: Path) -> None:
    root = tmp_path / ".portability" / "bigquery"
    path = root / "manifest.json"
    manifest = build_error_manifest("run_failed")
    assert manifest == {
        "schema_version": 1,
        "task": "PF-106",
        "dialect": "bigquery_google_sql",
        "execution_mode": "offline",
        "cloud_execution": "not_run",
        "verification": {"status": "error", "reason_code": "run_failed", "verifier_version": "1"},
    }
    write_manifest(path, manifest)
    assert validate_manifest(path, artifact_root=root) == manifest
    with pytest.raises(ManifestVerificationError, match="^manifest_invalid$"):
        verify_bundle(path, repository_root=tmp_path)
    with pytest.raises(ManifestVerificationError, match="^manifest_invalid$"):
        build_error_manifest("private traceback C:/secret " * 100)


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        (None, "schema_version", True),
        (None, "schema_version", 1.0),
        (None, "schema_version", 2),
        (None, "task", "other"),
        (None, "execution_mode", "cloud"),
        (None, "secret", "private"),
        ("query", "sha256", "bad"),
        ("query", "parser", "duckdb"),
        ("query", "dry_run_command", "bq query --execute"),
        ("fixture", "tables", True),
        ("fixture", "rows", {"alarms": -1}),
        ("reference", "result_rows", -1),
        ("reference", "engine", "bigquery"),
        ("verification", "reason_code", "private traceback"),
        ("verification", "verifier_version", "2"),
    ],
)
def test_manifest_rejects_invalid_fields(
    tmp_path: Path,
    section: str | None,
    key: str,
    value: object,
) -> None:
    manifest = success_manifest()
    (manifest if section is None else manifest[section])[key] = value
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestVerificationError) as error:
        validate_manifest(path, artifact_root=tmp_path)
    assert error.value.reason_code == "manifest_invalid"


@pytest.mark.parametrize("section", ["query", "schema", "fixture", "reference", "verification"])
def test_success_manifest_requires_every_section(tmp_path: Path, section: str) -> None:
    manifest = success_manifest()
    del manifest[section]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestVerificationError, match="^manifest_invalid$"):
        validate_manifest(path, artifact_root=tmp_path)


@pytest.mark.parametrize("path_value", ["../escape", "..\\escape", "/tmp/a", "C:/a", "a/../b"])
def test_manifest_rejects_nonrelative_or_traversing_paths(tmp_path: Path, path_value: str) -> None:
    manifest = success_manifest()
    manifest["query"]["path"] = path_value
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestVerificationError, match="^artifact_path_invalid$"):
        validate_manifest(path, artifact_root=tmp_path)


@pytest.mark.parametrize("content", ["{", "[]", "null", "\ufeff{}"])
def test_bad_json_has_bounded_reason(tmp_path: Path, content: str) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ManifestVerificationError, match="^manifest_invalid$"):
        validate_manifest(path, artifact_root=tmp_path)


def test_cloud_guard_has_specific_reason(tmp_path: Path) -> None:
    manifest = success_manifest()
    manifest["cloud_execution"] = "executed"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestVerificationError, match="^cloud_execution_not_offline$"):
        validate_manifest(path, artifact_root=tmp_path)


def test_io_preserves_utf8_and_lf_bytes(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "text.sql"
    write_text(path, "SELECT 'é';\n")
    assert path.read_bytes() == b"SELECT '\xc3\xa9';\n"
    assert file_sha256(path) == hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(path, {"z": 2, "a": 1})
    assert path.read_bytes() == b'{\n  "a": 1,\n  "z": 2\n}\n'


def test_external_root_fails_without_writing_error_manifest(tmp_path: Path) -> None:
    output = tmp_path / "outside"
    spec = RunSpec(repository_root=tmp_path, output_root=output)
    with pytest.raises(ValueError, match="artifact root"):
        run_bundle(spec)
    assert not output.exists()
    with pytest.raises(ManifestVerificationError, match="^artifact_path_invalid$"):
        verify_bundle(output / "manifest.json", repository_root=tmp_path)


def test_missing_source_writes_error_after_root_resolution(tmp_path: Path) -> None:
    output = tmp_path / ".portability" / "bigquery"
    spec = RunSpec(repository_root=tmp_path, output_root=output)
    with pytest.raises(ValueError, match="invalid portability schema"):
        run_bundle(spec)
    manifest = validate_manifest(output / "manifest.json", artifact_root=output)
    assert manifest == build_error_manifest("run_failed")
