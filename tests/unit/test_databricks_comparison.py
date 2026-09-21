from labs.portflow_databricks.comparison import build_comparison_report


def test_match_report_is_versioned_and_bounded() -> None:
    report = build_comparison_report(
        reference_manifest_sha256="a" * 64,
        reference_rows=1,
        reference_result_sha256="b" * 64,
        cloud_result_path="cloud-result.json",
        cloud_file_sha256="c" * 64,
        cloud_rows=1,
        cloud_result_sha256="b" * 64,
    )

    assert report["task"] == "PF-108"
    assert report["execution_mode"] == "manual_result_comparison"
    assert report["cloud_execution"] == "result_supplied"
    assert report["comparison"] == {
        "status": "match",
        "reason_code": None,
        "verifier_version": "1",
    }
