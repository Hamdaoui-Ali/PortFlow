import json
import shutil
from pathlib import Path

import pytest
from labs.portflow_databricks.runner import (
    ManifestVerificationError,
    RunSpec,
    run_bundle,
    verify_bundle,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def output_root(tmp_path: Path):
    root = ROOT / ".databricks" / "pf107" / f"test-{tmp_path.name}"
    yield root
    shutil.rmtree(root, ignore_errors=True)


def test_run_verify_and_repeat_have_identical_contract_hashes(
    output_root: Path,
) -> None:
    first = run_bundle(RunSpec(repository_root=ROOT, output_root=output_root / "first"))
    second = run_bundle(RunSpec(repository_root=ROOT, output_root=output_root / "second"))
    assert first["cloud_execution"] == "not_run"
    assert first["notebook"] == second["notebook"]
    assert first["schema"] == second["schema"]
    assert first["fixture"] == second["fixture"]
    assert first["expected_result"] == second["expected_result"]
    verify_bundle(output_root / "first" / "manifest.json", repository_root=ROOT)


@pytest.mark.parametrize(
    ("relative_path", "reason"),
    [
        ("portflow_delta_lab.py", "notebook_hash_mismatch"),
        ("schema.json", "schema_hash_mismatch"),
        ("expected-result.json", "result_hash_mismatch"),
    ],
)
def test_tampered_artifact_has_bounded_reason(
    output_root: Path,
    relative_path: str,
    reason: str,
) -> None:
    bundle = output_root / "bundle"
    run_bundle(RunSpec(repository_root=ROOT, output_root=bundle))
    target = bundle / relative_path
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ManifestVerificationError, match=reason):
        verify_bundle(bundle / "manifest.json", repository_root=ROOT)


def test_tampered_fixture_has_bounded_reason(output_root: Path) -> None:
    bundle = output_root / "fixture-tamper"
    run_bundle(RunSpec(repository_root=ROOT, output_root=bundle))
    target = bundle / "fixture" / "alarms" / "part-000000.parquet"
    target.write_bytes(target.read_bytes() + b"tamper")
    with pytest.raises(ManifestVerificationError, match="fixture_hash_mismatch"):
        verify_bundle(bundle / "manifest.json", repository_root=ROOT)


def test_input_fingerprint_is_deterministic(output_root: Path) -> None:
    bundle = output_root / "fingerprint"
    run_bundle(RunSpec(repository_root=ROOT, output_root=bundle))
    fingerprint = json.loads((bundle / "input-fingerprint.json").read_text(encoding="utf-8"))
    assert fingerprint["seed"] == 42
    assert (
        fingerprint["logical_sha256"]
        == json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))["fixture"]["sha256"]
    )
