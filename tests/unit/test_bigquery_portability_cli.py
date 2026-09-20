from pathlib import Path

from labs.portflow_bigquery.cli import main


def test_help_is_successful(capsys) -> None:
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "run" in output
    assert "verify" in output
    assert "cloud" not in output
    assert "network" not in output


def test_run_and_verify_use_local_artifact_defaults(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fake_run(spec):
        calls.append(f"run:{spec.project_id}:{spec.dataset}")
        return {"verification": {"status": "ok"}}

    def fake_verify(manifest_path, *, repository_root):
        calls.append(f"verify:{manifest_path.name}")

    monkeypatch.setattr("labs.portflow_bigquery.cli.run_bundle", fake_run)
    monkeypatch.setattr("labs.portflow_bigquery.cli.verify_bundle", fake_verify)

    assert main(["run", "--output", str(tmp_path / ".portability" / "bigquery")]) == 0
    assert main(
        ["verify", "--manifest", str(tmp_path / ".portability" / "bigquery" / "manifest.json")]
    ) == 0
    assert calls == ["run:demo-project:portflow", "verify:manifest.json"]


def test_cli_failure_does_not_print_exception_text(monkeypatch, capsys) -> None:
    class Failure(ValueError):
        reason_code = "query_hash_mismatch"

    def fail(*args, **kwargs):
        raise Failure("raw secret text")

    monkeypatch.setattr("labs.portflow_bigquery.cli.verify_bundle", fail)

    assert main(["verify", "--manifest", ".portability/bigquery/manifest.json"]) == 1
    output = capsys.readouterr().out
    assert "query_hash_mismatch" in output
    assert "raw secret text" not in output


def test_cli_failure_rejects_unsafe_reason_code(monkeypatch, capsys) -> None:
    class Failure(ValueError):
        reason_code = "secret text C:\\Users\\alice\\token"

    def fail(*args, **kwargs):
        raise Failure("raw secret text")

    monkeypatch.setattr("labs.portflow_bigquery.cli.verify_bundle", fail)

    assert main(["verify", "--manifest", ".portability/bigquery/manifest.json"]) == 1
    output = capsys.readouterr().out
    assert output == "portability verification failed: verification_failed\n"
    assert "secret text" not in output
    assert "alice" not in output


def test_cli_failure_rejects_reason_code_str_subclass(monkeypatch, capsys) -> None:
    class MaliciousReasonCode(str):
        def __str__(self) -> str:
            return "C:\\Users\\alice\\secret"

    class Failure(ValueError):
        reason_code = MaliciousReasonCode("query_hash_mismatch")

    def fail(*args, **kwargs):
        raise Failure("raw secret text")

    monkeypatch.setattr("labs.portflow_bigquery.cli.verify_bundle", fail)

    assert main(["verify", "--manifest", ".portability/bigquery/manifest.json"]) == 1
    output = capsys.readouterr().out
    assert output == "portability verification failed: verification_failed\n"
    assert "alice" not in output
    assert "secret" not in output


def test_cli_failure_rejects_reason_code_property(monkeypatch, capsys) -> None:
    class Failure(ValueError):
        @property
        def reason_code(self) -> str:
            raise RuntimeError("C:\\Users\\alice\\sensitive-secret")

    def fail(*args, **kwargs):
        raise Failure("raw secret text")

    monkeypatch.setattr("labs.portflow_bigquery.cli.verify_bundle", fail)

    assert main(["verify", "--manifest", ".portability/bigquery/manifest.json"]) == 1
    output = capsys.readouterr().out
    assert output == "portability verification failed: verification_failed\n"
    assert "alice" not in output
    assert "sensitive-secret" not in output
