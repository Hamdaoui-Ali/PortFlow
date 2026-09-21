from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import ANY

import pytest
from labs.portflow_bigquery.reference import (
    ReferenceExecutionError,
    run_local_reference,
)


def test_failed_dbt_reference_has_bounded_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FailedProcess:
        returncode = 1
        stdout = "secret-looking stdout"
        stderr = "secret-looking stderr"

    monkeypatch.setattr(
        "labs.portflow_bigquery.reference.subprocess.run",
        lambda *args, **kwargs: FailedProcess(),
    )
    (tmp_path / "fixture").mkdir()

    with pytest.raises(ReferenceExecutionError) as error:
        run_local_reference(
            repository_root=tmp_path,
            fixture_root=tmp_path / "fixture",
            gold_db=tmp_path / "gold" / "portflow.duckdb",
        )

    assert error.value.reason_code == "dbt_reference_failed"
    assert "secret-looking" not in str(error.value)


def test_unlaunchable_dbt_reference_has_bounded_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def raise_launch_error(*args: object, **kwargs: object) -> object:
        raise OSError("dbt missing at C:\\private\\dbt.exe")

    monkeypatch.setattr(
        "labs.portflow_bigquery.reference.subprocess.run", raise_launch_error
    )
    (tmp_path / "fixture").mkdir()

    with pytest.raises(ReferenceExecutionError) as error:
        run_local_reference(
            repository_root=tmp_path,
            fixture_root=tmp_path / "fixture",
            gold_db=tmp_path / "gold" / "portflow.duckdb",
        )

    assert error.value.reason_code == "dbt_reference_failed"
    assert "private" not in str(error.value)
    assert len(str(error.value)) < 100


def test_reference_requires_fixture_directory(tmp_path: Path) -> None:
    with pytest.raises(ReferenceExecutionError) as error:
        run_local_reference(
            repository_root=tmp_path,
            fixture_root=tmp_path / "missing",
            gold_db=tmp_path / "gold" / "portflow.duckdb",
        )

    assert error.value.reason_code == "fixture_missing"


def test_reference_requires_dbt_to_create_gold_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class SuccessfulProcess:
        returncode = 0

    monkeypatch.setattr(
        "labs.portflow_bigquery.reference.subprocess.run",
        lambda *args, **kwargs: SuccessfulProcess(),
    )
    fixture_root = tmp_path / "fixture"
    fixture_root.mkdir()

    with pytest.raises(ReferenceExecutionError) as error:
        run_local_reference(
            repository_root=tmp_path,
            fixture_root=fixture_root,
            gold_db=tmp_path / "gold" / "portflow.duckdb",
        )

    assert error.value.reason_code == "gold_output_missing"


def test_reference_runs_dbt_with_fixture_and_returns_canonical_gold_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class SuccessfulProcess:
        returncode = 0

    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> SuccessfulProcess:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SuccessfulProcess()

    records = [
        (
            "TM-001",
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
            3,
            4,
            2,
            15,
            1,
            10.0,
            1,
            1 / 3,
            1,
            30.0,
            0.75,
            2 / 3,
            10.0,
            1 / 3,
            1,
            1,
        ),
        (
            "TM-002",
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
            3,
            4,
            2,
            15,
            1,
            10.0,
            1,
            1 / 3,
            1,
            30.0,
            0.75,
            2 / 3,
            10.0,
            1 / 3,
            1,
            1,
        ),
    ]

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, query: str) -> "FakeConnection":
            captured["query"] = query
            return self

        def fetchall(self) -> list[tuple[object, ...]]:
            return records

    def fake_connect(*args: object, **kwargs: object) -> FakeConnection:
        captured["connect_args"] = args
        captured["connect_kwargs"] = kwargs
        return FakeConnection()

    monkeypatch.setattr("labs.portflow_bigquery.reference.subprocess.run", fake_run)
    monkeypatch.setattr("labs.portflow_bigquery.reference.duckdb.connect", fake_connect)
    monkeypatch.setenv("DBT_SEND_ANONYMOUS_USAGE_STATS", "true")
    fixture_root = tmp_path / "fixture"
    fixture_root.mkdir()
    gold_db = tmp_path / "gold" / "portflow.duckdb"
    gold_db.parent.mkdir()
    gold_db.touch()

    result = run_local_reference(
        repository_root=tmp_path,
        fixture_root=fixture_root,
        gold_db=gold_db,
    )

    assert captured["args"] == (
        [
            "dbt",
            "build",
            "--project-dir",
            str(tmp_path / "analytics"),
            "--profiles-dir",
            str(tmp_path / "analytics"),
        ],
    )
    assert captured["kwargs"] == {
        "check": False,
        "capture_output": True,
        "text": True,
        "cwd": tmp_path,
        "env": ANY,
    }
    environment = captured["kwargs"]["env"]
    assert isinstance(environment, dict)
    assert environment["DBT_SEND_ANONYMOUS_USAGE_STATS"] == "false"
    assert environment["PORTFLOW_SILVER_DIR"] == fixture_root.as_posix()
    assert environment["PORTFLOW_GOLD_DB"] == gold_db.as_posix()
    assert captured["connect_args"] == (str(gold_db),)
    assert captured["connect_kwargs"] == {"read_only": True}
    assert captured["query"] == (
        "SELECT terminal_id, source_period_start, source_period_end, "
        "available_intervals, scheduled_intervals, active_intervals, "
        "available_time_minutes, resolved_incident_count, repair_minutes, "
        "qualifying_failure_count, operating_hours, throughput, "
        "average_dwell_minutes, availability, utilization, mttr_minutes, "
        "mtbf_hours, active_incidents, critical_alarms FROM overview_kpis "
        "ORDER BY terminal_id"
    )
    assert result.rows[0]["terminal_id"] == "TM-001"
    assert result.rows[0]["source_period_start"] == "2026-01-01T00:00:00Z"
    assert result.rows[0]["operating_hours"] == 0.333333
    assert (
        result.result_sha256 == "eb1d401b2a44b8e3bfdc6238149fb5eff966710e170ec33aed80a54c60b61d3a"
    )
