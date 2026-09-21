import json
from pathlib import Path

import pytest
from labs.portflow_databricks.manifest import (
    ManifestVerificationError,
    build_error_manifest,
    build_manifest,
    validate_manifest,
    write_manifest,
)


def success_manifest() -> dict[str, object]:
    return build_manifest(
        notebook_sha256="a" * 64,
        schema_sha256="b" * 64,
        fixture_rows={
            "alarms": 2,
            "container_movements": 5,
            "incidents": 2,
            "telemetry_events": 4,
        },
        fixture_sha256="c" * 64,
        expected_rows=1,
        expected_sha256="d" * 64,
        result_sha256="e" * 64,
    )


def test_success_manifest_has_offline_pf107_contract() -> None:
    manifest = success_manifest()
    assert manifest["task"] == "PF-107"
    assert manifest["execution_mode"] == "offline_handoff"
    assert manifest["cloud_execution"] == "not_run"
    assert manifest["compute"] == "serverless"
    assert manifest["storage"] == "unity_catalog_volume_and_delta_tables"


def test_error_manifest_allows_only_safe_reason_codes() -> None:
    manifest = build_error_manifest("notebook_hash_mismatch")
    assert manifest["verification"] == {
        "status": "error",
        "reason_code": "notebook_hash_mismatch",
        "verifier_version": "1",
    }


def test_manifest_serialization_is_sorted_and_validated(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    write_manifest(path, success_manifest())
    assert validate_manifest(path, artifact_root=tmp_path) == success_manifest()
    expected = (json.dumps(success_manifest(), indent=2, sort_keys=True) + "\n").encode()
    assert path.read_bytes() == expected


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value.update({"task": "PF-999"}),
        lambda value: value["notebook"].update({"sha256": "bad"}),
        lambda value: value["fixture"]["rows"].update({"unknown": 1}),
        lambda value: value["verification"].update({"reason_code": "private traceback"}),
    ],
)
def test_manifest_rejects_invalid_fields(tmp_path: Path, change) -> None:
    manifest = success_manifest()
    change(manifest)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestVerificationError, match="^manifest_invalid$"):
        validate_manifest(path, artifact_root=tmp_path)


@pytest.mark.parametrize("relative_path", ["../escape", r"..\escape", "/tmp/a", "C:/a"])
def test_manifest_rejects_unsafe_declared_paths(tmp_path: Path, relative_path: str) -> None:
    manifest = success_manifest()
    manifest["notebook"]["path"] = relative_path
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestVerificationError, match="^artifact_path_invalid$"):
        validate_manifest(path, artifact_root=tmp_path)


def test_manifest_rejects_cloud_execution(tmp_path: Path) -> None:
    manifest = success_manifest()
    manifest["cloud_execution"] = "executed"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestVerificationError, match="^cloud_execution_not_offline$"):
        validate_manifest(path, artifact_root=tmp_path)
