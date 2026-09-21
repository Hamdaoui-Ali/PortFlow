import json
import shutil
from pathlib import Path

import pytest
from labs.portflow_databricks.comparison import (
    ComparisonSpec,
    ComparisonVerificationError,
    compare_result,
    verify_comparison,
)
from labs.portflow_databricks.runner import RunSpec, run_bundle

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def comparison_paths(tmp_path: Path):
    suffix = tmp_path.name
    handoff = ROOT / ".databricks" / "pf107" / f"comparison-{suffix}"
    output = ROOT / ".databricks" / "pf108" / f"comparison-{suffix}"
    try:
        yield handoff, output
    finally:
        shutil.rmtree(handoff, ignore_errors=True)
        shutil.rmtree(output, ignore_errors=True)


def _prepare_comparison(comparison_paths) -> ComparisonSpec:
    handoff, output = comparison_paths
    run_bundle(RunSpec(repository_root=ROOT, output_root=handoff))
    output.mkdir(parents=True, exist_ok=True)
    cloud_result = output / "cloud-result.json"
    shutil.copy2(handoff / "expected-result.json", cloud_result)
    return ComparisonSpec(
        repository_root=ROOT,
        handoff_manifest=handoff / "manifest.json",
        cloud_result=cloud_result,
        output_path=output / "comparison.json",
    )


def test_matching_comparison_is_repeatable_and_verifiable(comparison_paths) -> None:
    spec = _prepare_comparison(comparison_paths)
    first = compare_result(spec)
    first_bytes = spec.output_path.read_bytes()
    second = compare_result(spec)

    assert first == second
    assert first_bytes == spec.output_path.read_bytes()
    assert first["comparison"] == {
        "status": "match",
        "reason_code": None,
        "verifier_version": "1",
    }
    verify_comparison(spec.output_path, repository_root=ROOT)


def test_semantic_mismatch_is_a_valid_non_matching_report(comparison_paths) -> None:
    spec = _prepare_comparison(comparison_paths)
    rows = json.loads(spec.cloud_result.read_text(encoding="utf-8"))
    rows[0]["throughput"] += 1
    spec.cloud_result.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    report = compare_result(spec)

    assert report["comparison"] == {
        "status": "mismatch",
        "reason_code": "result_hash_mismatch",
        "verifier_version": "1",
    }
    verify_comparison(spec.output_path, repository_root=ROOT)


def test_changed_cloud_file_has_a_bounded_verification_reason(comparison_paths) -> None:
    spec = _prepare_comparison(comparison_paths)
    compare_result(spec)
    spec.cloud_result.write_text(
        spec.cloud_result.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )

    with pytest.raises(ComparisonVerificationError, match="^cloud_result_hash_mismatch$"):
        verify_comparison(spec.output_path, repository_root=ROOT)


def test_changed_handoff_has_a_bounded_verification_reason(comparison_paths) -> None:
    spec = _prepare_comparison(comparison_paths)
    compare_result(spec)
    result_path = spec.handoff_manifest.parent / "expected-result.json"
    result_path.write_text(result_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ComparisonVerificationError, match="^handoff_invalid$"):
        verify_comparison(spec.output_path, repository_root=ROOT)


def test_changed_report_has_a_bounded_verification_reason(comparison_paths) -> None:
    spec = _prepare_comparison(comparison_paths)
    compare_result(spec)
    report = json.loads(spec.output_path.read_text(encoding="utf-8"))
    report["reference"]["result_sha256"] = "0" * 64
    spec.output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ComparisonVerificationError, match="^comparison_invalid$"):
        verify_comparison(spec.output_path, repository_root=ROOT)


def test_comparison_does_not_change_public_data(comparison_paths) -> None:
    public_root = ROOT / "web" / "public" / "data"
    before = {
        path.relative_to(public_root): path.read_bytes()
        for path in public_root.rglob("*")
        if path.is_file()
    }

    spec = _prepare_comparison(comparison_paths)
    compare_result(spec)

    after = {
        path.relative_to(public_root): path.read_bytes()
        for path in public_root.rglob("*")
        if path.is_file()
    }
    assert after == before
