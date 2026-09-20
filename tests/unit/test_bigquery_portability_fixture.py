import os
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
from labs.portflow_bigquery.fixture import (
    FixtureSpec,
    generate_fixture,
    logical_fixture_hash,
)
from labs.portflow_bigquery.schema import load_schema

ROOT = Path(__file__).parents[2]
SCHEMA_PATH = ROOT / "analytics" / "portability" / "bigquery" / "schema.json"


def _link_directory(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        if os.name != "nt":
            raise OSError("directory links unavailable") from error
        result = os.system(
            f'cmd.exe /c mklink /J "{link}" "{target}" >nul 2>nul'
        )
        if result != 0:
            raise OSError("directory links unavailable") from error


def test_fixture_covers_kpi_edge_cases(tmp_path: Path) -> None:
    schema = load_schema(SCHEMA_PATH)
    fixture_root = tmp_path / ".portability" / "bigquery" / "fixture"
    metadata = generate_fixture(
        FixtureSpec(seed=42),
        fixture_root,
        schema_path=SCHEMA_PATH,
        repository_root=tmp_path,
    )

    assert metadata.rows_by_table == {
        "telemetry_events": 4,
        "container_movements": 5,
        "incidents": 2,
        "alarms": 2,
    }
    telemetry = pl.read_parquet(
        fixture_root / "telemetry_events" / "part-000000.parquet"
    )
    assert telemetry.select("state", "available").to_dicts() == [
        {"state": "ACTIVE", "available": True},
        {"state": "IDLE", "available": True},
        {"state": "UNAVAILABLE", "available": False},
        {"state": "ACTIVE", "available": True},
    ]
    assert pl.read_parquet(
        fixture_root / "container_movements" / "part-000000.parquet"
    ).select("movement_type", "container_ref", "event_timestamp").to_dicts() == [
        {
            "movement_type": "GATE_IN",
            "container_ref": "CONT-000001",
            "event_timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        },
        {
            "movement_type": "LOAD",
            "container_ref": "CONT-000001",
            "event_timestamp": datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        },
        {
            "movement_type": "DISCHARGE",
            "container_ref": "CONT-000001",
            "event_timestamp": datetime(2026, 1, 1, 0, 20, tzinfo=UTC),
        },
        {
            "movement_type": "GATE_OUT",
            "container_ref": "CONT-000001",
            "event_timestamp": datetime(2026, 1, 1, 0, 30, tzinfo=UTC),
        },
        {
            "movement_type": "GATE_IN",
            "container_ref": "CONT-000002",
            "event_timestamp": datetime(2026, 1, 1, 0, 10, tzinfo=UTC),
        },
    ]
    assert schema["incidents"]


def test_fixture_hash_is_repeatable_and_independent_of_file_names(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_fixture = first / ".portability" / "bigquery" / "fixture"
    second_fixture = second / ".portability" / "bigquery" / "fixture"
    schema = load_schema(SCHEMA_PATH)

    first_metadata = generate_fixture(
        FixtureSpec(seed=42),
        first_fixture,
        schema_path=SCHEMA_PATH,
        repository_root=first,
    )
    second_metadata = generate_fixture(
        FixtureSpec(seed=42),
        second_fixture,
        schema_path=SCHEMA_PATH,
        repository_root=second,
    )

    assert first_metadata.logical_sha256 == second_metadata.logical_sha256

    telemetry_root = first_fixture / "telemetry_events"
    telemetry = pl.read_parquet(telemetry_root / "part-000000.parquet")
    telemetry.tail(2).write_parquet(telemetry_root / "part-000000.parquet")
    telemetry.head(2).write_parquet(telemetry_root / "part-000001.parquet")
    assert logical_fixture_hash(first_fixture, schema) == second_metadata.logical_sha256
    assert logical_fixture_hash(first_fixture, schema) == logical_fixture_hash(
        second_fixture, schema
    )


def test_fixture_writer_rejects_output_outside_artifact_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="artifact root"):
        generate_fixture(
            FixtureSpec(seed=42),
            tmp_path / "outside" / "fixture",
            schema_path=SCHEMA_PATH,
            repository_root=tmp_path,
        )


def test_fixture_writer_rejects_linked_artifact_root(tmp_path: Path) -> None:
    portability_root = tmp_path / ".portability"
    portability_root.mkdir()
    outside = tmp_path / "outside-root"
    outside.mkdir()
    linked_root = portability_root / "bigquery"
    try:
        _link_directory(linked_root, outside)
    except OSError as error:
        pytest.skip(f"directory links unavailable: {error}")

    with pytest.raises(ValueError, match="artifact root"):
        generate_fixture(
            FixtureSpec(seed=42),
            linked_root / "fixture",
            schema_path=SCHEMA_PATH,
            repository_root=tmp_path,
        )
    assert not list(outside.iterdir())


def test_fixture_writer_rejects_linked_table_root(tmp_path: Path) -> None:
    fixture_root = tmp_path / ".portability" / "bigquery" / "fixture"
    fixture_root.mkdir(parents=True)
    outside = tmp_path / "outside-table"
    outside.mkdir()
    try:
        _link_directory(fixture_root / "telemetry_events", outside)
    except OSError as error:
        pytest.skip(f"directory links unavailable: {error}")

    with pytest.raises(ValueError, match="artifact path"):
        generate_fixture(
            FixtureSpec(seed=42),
            fixture_root,
            schema_path=SCHEMA_PATH,
            repository_root=tmp_path,
        )
    assert not list(outside.iterdir())
