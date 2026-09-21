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
