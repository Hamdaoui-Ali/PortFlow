import shutil
from pathlib import Path

from labs.portflow_databricks.cli import main

ROOT = Path(__file__).resolve().parents[2]


def test_cli_run_and_verify_print_bounded_success(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(ROOT)
    output = ROOT / ".databricks" / "pf107" / f"cli-{tmp_path.name}"
    try:
        assert main(["run", "--output", str(output)]) == 0
        assert capsys.readouterr().out == "databricks handoff bundle verified\n"
        assert main(["verify", "--manifest", str(output / "manifest.json")]) == 0
        assert capsys.readouterr().out == "databricks handoff bundle verified\n"
    finally:
        shutil.rmtree(output, ignore_errors=True)


def test_cli_failure_output_is_bounded(monkeypatch, capsys) -> None:
    class Failure(ValueError):
        reason_code = "notebook_hash_mismatch"

    def fail(*args, **kwargs):
        raise Failure("C:\\Users\\alice\\secret")

    monkeypatch.setattr("labs.portflow_databricks.cli.verify_bundle", fail)
    assert main(["verify", "--manifest", ".databricks/pf107/manifest.json"]) == 1
    output = capsys.readouterr().out
    assert output == "databricks verification failed: notebook_hash_mismatch\n"
    assert "alice" not in output
    assert "secret" not in output


def test_cli_unknown_failure_reason_is_mapped(monkeypatch, capsys) -> None:
    class Failure(ValueError):
        reason_code = "private_traceback"

    monkeypatch.setattr(
        "labs.portflow_databricks.cli.verify_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(Failure("secret")),
    )
    assert main(["verify", "--manifest", ".databricks/pf107/manifest.json"]) == 1
    assert capsys.readouterr().out == "databricks verification failed: run_failed\n"


def test_cli_invalid_arguments_return_two(capsys) -> None:
    assert main(["verify"]) == 2
    capsys.readouterr()


def test_cli_compare_defaults_and_match_output(monkeypatch, capsys) -> None:
    captured = []

    def fake_compare(spec):
        captured.append(spec)
        return {"comparison": {"status": "match", "reason_code": None}}

    monkeypatch.setattr("labs.portflow_databricks.cli.compare_result", fake_compare)

    assert main(["compare"]) == 0
    assert capsys.readouterr().out == "databricks comparison matched\n"
    assert captured[0].handoff_manifest == Path(".databricks/pf107/manifest.json")
    assert captured[0].cloud_result == Path(".databricks/pf108/cloud-result.json")
    assert captured[0].output_path == Path(".databricks/pf108/comparison.json")


def test_cli_compare_returns_one_for_semantic_mismatch(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "labs.portflow_databricks.cli.compare_result",
        lambda spec: {
            "comparison": {
                "status": "mismatch",
                "reason_code": "result_hash_mismatch",
            }
        },
    )

    assert main(["compare"]) == 1
    assert capsys.readouterr().out == ("databricks comparison mismatch: result_hash_mismatch\n")


def test_cli_compare_failure_output_is_bounded(monkeypatch, capsys) -> None:
    class Failure(ValueError):
        reason_code = "cloud_result_invalid"

    def fail(*args, **kwargs):
        raise Failure("C:\\Users\\alice\\secret")

    monkeypatch.setattr("labs.portflow_databricks.cli.compare_result", fail)

    assert main(["compare"]) == 1
    output = capsys.readouterr().out
    assert output == "databricks comparison failed: cloud_result_invalid\n"
    assert "alice" not in output
    assert "secret" not in output


def test_cli_compare_rejects_hostile_reason_descriptor(monkeypatch, capsys) -> None:
    class Failure(ValueError):
        @property
        def reason_code(self):
            raise RuntimeError("C:\\Users\\alice\\secret")

    monkeypatch.setattr(
        "labs.portflow_databricks.cli.compare_result",
        lambda *args, **kwargs: (_ for _ in ()).throw(Failure("raw secret")),
    )

    assert main(["compare"]) == 1
    output = capsys.readouterr().out
    assert output == "databricks comparison failed: comparison_invalid\n"
    assert "alice" not in output
    assert "secret" not in output
