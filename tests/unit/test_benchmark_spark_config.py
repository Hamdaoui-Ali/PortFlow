from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from benchmarks.portflow_benchmarks import spark_runner, spark_worker
from benchmarks.portflow_benchmarks.models import WorkloadSpec
from benchmarks.portflow_benchmarks.spark_runner import (
    build_compose_command,
    failure_execution,
    validate_artifact_paths,
)

REPOSITORY_ROOT = Path(__file__).parents[2]
COMPOSE_PATH = REPOSITORY_ROOT / "benchmarks" / "spark" / "compose.yaml"
START = datetime(2026, 1, 1, tzinfo=UTC)
WORKLOAD = WorkloadSpec(window_start=START, window_end=START + timedelta(hours=1))


def test_spark_compose_is_pinned_and_isolated() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    service = compose["services"]["pyspark"]
    volumes = service["volumes"]

    assert service["image"] == (
        "apache/spark@sha256:"
        "a89782d90529a623fc4471cdddb0f9c32d6eed10a81b256a80207b23c3b1df00"
    )
    assert service["entrypoint"] == ["/opt/spark/bin/spark-submit"]
    assert service["working_dir"] == "/tmp"
    assert "spark_worker.py" in " ".join(service["command"])
    assert any(str(volume).endswith("/workspace/fixture:ro") for volume in volumes)
    assert any(str(volume).endswith("/workspace/benchmarks:ro") for volume in volumes)
    assert any(str(volume).endswith("/workspace/output") for volume in volumes)
    assert not service.get("ports")
    assert not compose.get("volumes")


def test_default_compose_has_no_benchmark_service() -> None:
    root_compose = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8").lower()

    assert "pyspark" not in root_compose
    assert "benchmarks/spark" not in root_compose


def test_spark_worker_resolves_the_mounted_benchmark_package() -> None:
    assert spark_worker._PACKAGE_ROOT == REPOSITORY_ROOT / "benchmarks"


def test_spark_command_uses_local_submit_and_bounded_mount_inputs(tmp_path: Path) -> None:
    fixture_root = REPOSITORY_ROOT / ".benchmarks" / "fixtures"
    output_root = REPOSITORY_ROOT / ".benchmarks" / "spark"
    fixture_dir = fixture_root / "smoke"
    output_dir = output_root / "run"

    command, environment = build_compose_command(fixture_dir, WORKLOAD, output_dir)

    assert command[:5] == [
        "docker",
        "compose",
        "-f",
        "benchmarks/spark/compose.yaml",
        "run",
    ]
    assert "--rm" in command
    assert "pyspark" in command
    assert environment["PF_BENCHMARK_FIXTURE_SUBPATH"] == "smoke"
    assert environment["PF_BENCHMARK_WINDOW_START"].endswith("Z")
    assert environment["PF_BENCHMARK_WINDOW_END"].endswith("Z")
    assert environment["PF_BENCHMARK_OUTPUT_NAME"] == "run/result.json"


def test_spark_runner_rejects_paths_outside_benchmark_artifacts(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="within benchmark artifacts"):
        validate_artifact_paths(tmp_path / "fixture", tmp_path / "output")


def test_spark_failure_metadata_is_bounded_and_safe() -> None:
    execution = failure_execution("docker_unavailable")

    assert execution.status == "unavailable"
    assert execution.reason_code == "docker_unavailable"
    assert len(execution.reason_code or "") <= 64
    assert execution.result_sha256 == ""
    assert execution.result_rows == ()


def test_spark_worker_rejects_output_outside_mount(tmp_path: Path, monkeypatch) -> None:
    output_root = tmp_path / "output"
    monkeypatch.setattr(spark_worker, "_OUTPUT_ROOT", output_root, raising=False)

    with pytest.raises(ValueError, match="within Spark output"):
        spark_worker._write_payload(tmp_path / "outside" / "result.json", {})


def test_spark_runner_rejects_symlinked_output_root(tmp_path: Path, monkeypatch) -> None:
    fixture_root = tmp_path / "fixtures"
    fixture_dir = fixture_root / "smoke"
    fixture_dir.mkdir(parents=True)
    target_root = tmp_path / "target-spark"
    target_root.mkdir()
    linked_root = tmp_path / "spark"
    try:
        linked_root.symlink_to(target_root, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory links unavailable: {error}")

    monkeypatch.setattr(spark_runner, "FIXTURE_ROOT", fixture_root)
    monkeypatch.setattr(spark_runner, "SPARK_ROOT", linked_root)
    with pytest.raises(ValueError, match="artifact root"):
        spark_runner.validate_artifact_paths(fixture_dir, linked_root / "run")
