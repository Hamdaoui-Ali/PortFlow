"""Offline generation and verification of the PF-107 handoff bundle."""

import json
import shutil
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import duckdb
import polars as pl

from labs.portflow_bigquery.canonical import result_sha256
from labs.portflow_bigquery.fixture import (
    FixtureMetadata,
    FixtureSpec,
    generate_fixture,
    logical_fixture_hash,
)
from labs.portflow_bigquery.reference import run_local_reference
from labs.portflow_bigquery.schema import load_schema

from .manifest import (
    FINGERPRINT_FILE,
    MANIFEST_FILE,
    NOTEBOOK_FILE,
    RESULT_FILE,
    SCHEMA_FILE,
    ManifestVerificationError,
    build_error_manifest,
    build_manifest,
    file_sha256,
    validate_manifest,
    write_json,
    write_manifest,
)
from .notebook import NotebookValidationError, notebook_sha256, validate_notebook_file
from .paths import ArtifactPathError, resolve_artifact_path, resolve_artifact_root


@dataclass(frozen=True)
class RunSpec:
    """Inputs for a local, credential-free PF-107 bundle generation."""

    repository_root: Path
    output_root: Path
    seed: int = 42


def _artifact_path(root: Path, relative_path: str) -> Path:
    try:
        return resolve_artifact_path(root, relative_path)
    except ArtifactPathError:
        raise ManifestVerificationError("artifact_path_invalid") from None


def _copy_bytes(root: Path, relative_path: str, content: bytes) -> Path:
    target = _artifact_path(root, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def _generate_fixture(spec: RunSpec, root: Path, schema_path: Path) -> FixtureMetadata:
    """Generate through PF-106's fixture code in a disposable staging root."""
    with TemporaryDirectory(prefix="portflow-pf107-fixture-") as staging:
        staging_root = Path(staging)
        staged_fixture = staging_root / ".portability" / "bigquery" / "fixture"
        metadata = generate_fixture(
            FixtureSpec(seed=spec.seed),
            staged_fixture,
            schema_path=schema_path,
            repository_root=staging_root,
        )
        target = _artifact_path(root, "fixture")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(staged_fixture, target)
    return metadata


def _run_reference(
    repository_root: Path,
    fixture_root: Path,
) -> tuple[tuple[dict[str, object], ...], str]:
    """Run the existing disposable dbt/DuckDB reference without touching the repo."""
    with TemporaryDirectory(prefix="portflow-pf107-reference-") as reference:
        reference_root = Path(reference)
        shutil.copytree(
            repository_root / "analytics",
            reference_root / "analytics",
            ignore=shutil.ignore_patterns("target", "logs", ".user.yml"),
        )
        selectors = reference_root / "analytics" / "selectors.yml"
        selectors.write_text(
            "selectors:\n  - name: portability_reference\n"
            "    default: true\n    definition: '+overview_kpis'\n",
            encoding="utf-8",
            newline="",
        )
        reference_result = run_local_reference(
            repository_root=reference_root,
            fixture_root=fixture_root,
            gold_db=reference_root / "portflow.duckdb",
        )
    return reference_result.rows, reference_result.result_sha256


def run_bundle(spec: RunSpec) -> dict[str, object]:
    """Generate and verify a deterministic local bundle, or record run_failed."""
    root = resolve_artifact_root(spec.output_root, repository_root=spec.repository_root)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = _artifact_path(root, MANIFEST_FILE)
    try:
        source_root = spec.repository_root / "analytics" / "portability" / "bigquery"
        notebook_source_path = (
            spec.repository_root / "labs" / "portflow_databricks" / "notebooks" / NOTEBOOK_FILE
        )
        schema_source_path = source_root / SCHEMA_FILE
        notebook_bytes = notebook_source_path.read_bytes()
        notebook_source = notebook_bytes.decode("utf-8")
        validate_notebook_file(notebook_source_path)
        _copy_bytes(root, NOTEBOOK_FILE, notebook_bytes)
        _copy_bytes(root, SCHEMA_FILE, schema_source_path.read_bytes())

        fixture = _generate_fixture(spec, root, schema_source_path)
        rows, reference_hash = _run_reference(spec.repository_root, _artifact_path(root, "fixture"))
        result_path = _artifact_path(root, RESULT_FILE)
        write_json(result_path, list(rows))
        write_json(_artifact_path(root, FINGERPRINT_FILE), fixture.as_json())
        manifest = build_manifest(
            notebook_sha256=notebook_sha256(notebook_source),
            schema_sha256=file_sha256(_artifact_path(root, SCHEMA_FILE)),
            fixture_rows=fixture.rows_by_table,
            fixture_sha256=fixture.logical_sha256,
            expected_rows=len(rows),
            expected_sha256=file_sha256(result_path),
            result_sha256=reference_hash,
        )
        write_manifest(manifest_path, manifest)
        verify_bundle(manifest_path, repository_root=spec.repository_root)
        return manifest
    except (OSError, UnicodeError, ValueError, TypeError, pl.exceptions.PolarsError, duckdb.Error):
        with suppress(OSError, ValueError, TypeError):
            write_manifest(manifest_path, build_error_manifest("run_failed"))
        raise ManifestVerificationError("run_failed") from None


def _verify_fixture(root: Path, fixture: dict[str, object], schema_path: Path) -> None:
    try:
        fields = load_schema(schema_path)
        fixture_root = _artifact_path(root, "fixture")
        rows: dict[str, int] = {}
        for table_name, table_fields in fields.items():
            table_root = _artifact_path(fixture_root, table_name)
            parts = sorted(table_root.glob("*.parquet"))
            if not parts:
                raise ValueError
            table_rows = 0
            for part in parts:
                safe_part = _artifact_path(table_root, part.name)
                table_rows += pl.read_parquet(safe_part).height
            rows[table_name] = table_rows
            if not table_fields:
                raise ValueError
        if rows != fixture["rows"]:
            raise ValueError
        if logical_fixture_hash(fixture_root, fields) != fixture["sha256"]:
            raise ValueError
    except ManifestVerificationError:
        raise
    except (OSError, ValueError, TypeError, pl.exceptions.PolarsError):
        raise ManifestVerificationError("fixture_hash_mismatch") from None


def _verify_result(path: Path, expected: dict[str, object]) -> None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list) or len(raw) != expected["rows"]:
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
        if result_sha256(rows) != expected["result_sha256"]:
            raise ValueError
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, OverflowError):
        raise ManifestVerificationError("result_hash_mismatch") from None


def verify_bundle(manifest_path: Path, *, repository_root: Path) -> None:
    """Verify hashes and contracts without running dbt or contacting Databricks."""
    try:
        root = resolve_artifact_root(manifest_path.parent, repository_root=repository_root)
    except ArtifactPathError:
        raise ManifestVerificationError("artifact_path_invalid") from None
    manifest = validate_manifest(manifest_path, artifact_root=root)
    verification = cast(dict[str, object], manifest["verification"])
    if verification["status"] != "ok":
        raise ManifestVerificationError("manifest_invalid")

    notebook = cast(dict[str, object], manifest["notebook"])
    notebook_path = _artifact_path(root, cast(str, notebook["path"]))
    try:
        if file_sha256(notebook_path) != notebook["sha256"]:
            raise ValueError
    except (OSError, ValueError):
        raise ManifestVerificationError("notebook_hash_mismatch") from None
    try:
        validate_notebook_file(notebook_path)
    except (NotebookValidationError, OSError, UnicodeError):
        raise ManifestVerificationError("notebook_contract_invalid") from None

    schema = cast(dict[str, object], manifest["schema"])
    schema_path = _artifact_path(root, cast(str, schema["path"]))
    try:
        if file_sha256(schema_path) != schema["sha256"]:
            raise ValueError
        load_schema(schema_path)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        raise ManifestVerificationError("schema_hash_mismatch") from None

    fixture = cast(dict[str, object], manifest["fixture"])
    _verify_fixture(root, fixture, schema_path)

    expected = cast(dict[str, object], manifest["expected_result"])
    result_path = _artifact_path(root, cast(str, expected["path"]))
    try:
        if file_sha256(result_path) != expected["sha256"]:
            raise ValueError
    except (OSError, ValueError):
        raise ManifestVerificationError("result_hash_mismatch") from None
    _verify_result(result_path, expected)
