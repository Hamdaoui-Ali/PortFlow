"""Offline orchestration and verification of the PF-106 artifact bundle."""

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import duckdb
import polars as pl

from .canonical import result_sha256
from .fixture import FixtureSpec, generate_fixture, logical_fixture_hash
from .manifest import (
    DRY_RUN_COMMAND,
    ManifestVerificationError,
    build_error_manifest,
    build_manifest,
    file_sha256,
    validate_manifest,
    write_json,
    write_manifest,
    write_text,
)
from .paths import ArtifactPathError, resolve_artifact_path, resolve_artifact_root
from .query import QueryValidationError, query_sha256, render_query, validate_google_sql
from .reference import run_local_reference
from .schema import load_schema

_QUERY_FILE = "overview_kpis.sql"
_SCHEMA_FILE = "schema.json"
_MANIFEST_FILE = "manifest.json"
_RESULT_FILE = "expected-result.json"
_FINGERPRINT_FILE = "input-fingerprint.json"


@dataclass(frozen=True)
class RunSpec:
    """Local paths and identifiers; project/dataset never initiate a connection."""

    repository_root: Path
    output_root: Path
    project_id: str = "demo-project"
    dataset: str = "portflow"
    seed: int = 42


def run_bundle(spec: RunSpec) -> dict[str, object]:
    """Build, record, and verify a local bundle; record bounded known failures."""
    root = resolve_artifact_root(spec.output_root, repository_root=spec.repository_root)
    manifest_path = resolve_artifact_path(root, _MANIFEST_FILE)
    try:
        source = spec.repository_root / "analytics" / "portability" / "bigquery"
        fixture = generate_fixture(
            FixtureSpec(seed=spec.seed),
            root / "fixture",
            schema_path=source / _SCHEMA_FILE,
            repository_root=spec.repository_root,
        )
        template = (source / "overview_kpis.sql").read_text(encoding="utf-8")
        query = render_query(template, project_id=spec.project_id, dataset=spec.dataset)
        validate_google_sql(query)
        write_text(root / _QUERY_FILE, query)
        write_text(root / _SCHEMA_FILE, (source / _SCHEMA_FILE).read_text(encoding="utf-8"))
        with TemporaryDirectory(prefix="portflow-pf106-") as reference_root:
            reference_repository = Path(reference_root)
            # The production project also contains maintenance_orders, outside
            # this four-table contract. Select the KPI and its ancestors only
            # in a disposable project, keeping production analytics untouched.
            reference_project = reference_repository / "analytics"
            shutil.copytree(
                spec.repository_root / "analytics",
                reference_project,
                ignore=shutil.ignore_patterns("target", "logs", ".user.yml"),
            )
            write_text(
                reference_project / "selectors.yml",
                "selectors:\n  - name: portability_reference\n"
                "    default: true\n    definition: '+overview_kpis'\n",
            )
            reference = run_local_reference(
                repository_root=reference_repository,
                fixture_root=root / "fixture",
                gold_db=reference_repository / "portflow.duckdb",
            )
        write_json(root / _RESULT_FILE, list(reference.rows))
        write_json(root / _FINGERPRINT_FILE, fixture.as_json())
        manifest = build_manifest(
            query_sha256=query_sha256(query),
            schema_sha256=file_sha256(root / _SCHEMA_FILE),
            fixture=fixture,
            reference=reference,
            dry_run_command=DRY_RUN_COMMAND,
        )
        write_manifest(manifest_path, manifest)
        verify_bundle(manifest_path, repository_root=spec.repository_root)
        return manifest
    except (OSError, ValueError, pl.exceptions.PolarsError, duckdb.Error):
        write_manifest(manifest_path, build_error_manifest("run_failed"))
        raise


def _artifact_path(root: Path, name: str) -> Path:
    try:
        return resolve_artifact_path(root, name)
    except ArtifactPathError:
        raise ManifestVerificationError("artifact_path_invalid") from None


def _verify_result(path: Path, reference: dict[str, object]) -> None:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list) or len(rows) != reference["result_rows"]:
            raise ValueError
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError
            # canonical.py deliberately accepts aware datetime inputs only.
            # Decode the on-disk canonical UTC timestamps before reusing it.
            for field in ("source_period_start", "source_period_end"):
                value = row.get(field)
                if not isinstance(value, str) or not value.endswith("Z"):
                    raise ValueError
                row[field] = datetime.fromisoformat(value)
        if result_sha256(rows) != reference["result_sha256"]:
            raise ValueError
    except (OSError, ValueError, TypeError, OverflowError):
        raise ManifestVerificationError("result_hash_mismatch") from None


def verify_bundle(manifest_path: Path, *, repository_root: Path) -> None:
    """Recompute artifact hashes and parse GoogleSQL, without running dbt or bq."""
    try:
        root = resolve_artifact_root(manifest_path.parent, repository_root=repository_root)
    except ArtifactPathError:
        raise ManifestVerificationError("artifact_path_invalid") from None
    manifest = validate_manifest(manifest_path, artifact_root=root)
    verification = cast(dict[str, object], manifest["verification"])
    if verification["status"] != "ok":
        raise ManifestVerificationError("manifest_invalid")
    query = cast(dict[str, object], manifest["query"])
    schema = cast(dict[str, object], manifest["schema"])
    fixture = cast(dict[str, object], manifest["fixture"])
    reference = cast(dict[str, object], manifest["reference"])
    query_path = _artifact_path(root, cast(str, query["path"]))
    schema_path = _artifact_path(root, cast(str, schema["path"]))
    fixture_root = _artifact_path(root, "fixture")
    result_path = _artifact_path(root, "expected-result.json")
    try:
        sql = query_path.read_text(encoding="utf-8")
        if query_sha256(sql) != query["sha256"]:
            raise ValueError
    except (OSError, ValueError):
        raise ManifestVerificationError("query_hash_mismatch") from None
    try:
        validate_google_sql(sql)
    except QueryValidationError:
        raise ManifestVerificationError("manifest_invalid") from None
    try:
        if file_sha256(schema_path) != schema["sha256"]:
            raise ValueError
        fields = load_schema(schema_path)
    except (OSError, ValueError):
        raise ManifestVerificationError("schema_hash_mismatch") from None
    # The logical hash helper reads Parquet directly. Guard every directory and
    # file before calling it so linked inputs cannot escape the artifact root.
    try:
        for table in fields:
            table_root = _artifact_path(fixture_root, table)
            for part in table_root.glob("*.parquet"):
                _artifact_path(table_root, part.name)
        if logical_fixture_hash(fixture_root, fields) != fixture["sha256"]:
            raise ValueError
    except ManifestVerificationError:
        raise
    except (OSError, ValueError, pl.exceptions.PolarsError):
        raise ManifestVerificationError("fixture_hash_mismatch") from None
    _verify_result(result_path, reference)
