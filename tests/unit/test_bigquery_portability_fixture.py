from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from labs.portflow_bigquery.fixture import (
    FixtureSpec,
    generate_fixture,
    logical_fixture_hash,
)
from labs.portflow_bigquery.schema import load_schema

ROOT = Path(__file__).parents[2]
SCHEMA_PATH = ROOT / "analytics" / "portability" / "bigquery" / "schema.json"


def test_fixture_covers_kpi_edge_cases(tmp_path: Path) -> None:
    schema = load_schema(SCHEMA_PATH)
    metadata = generate_fixture(
        FixtureSpec(seed=42), tmp_path / "fixture", schema_path=SCHEMA_PATH
    )

    assert metadata.rows_by_table == {
        "telemetry_events": 4,
        "container_movements": 5,
        "incidents": 2,
        "alarms": 2,
    }
    telemetry = pl.read_parquet(
        tmp_path / "fixture" / "telemetry_events" / "part-000000.parquet"
    )
    assert telemetry.select("state", "available").to_dicts() == [
        {"state": "ACTIVE", "available": True},
        {"state": "IDLE", "available": True},
        {"state": "UNAVAILABLE", "available": False},
        {"state": "ACTIVE", "available": True},
    ]
    assert pl.read_parquet(
        tmp_path / "fixture" / "container_movements" / "part-000000.parquet"
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
    schema = load_schema(SCHEMA_PATH)

    first_metadata = generate_fixture(FixtureSpec(seed=42), first, schema_path=SCHEMA_PATH)
    second_metadata = generate_fixture(FixtureSpec(seed=42), second, schema_path=SCHEMA_PATH)

    assert first_metadata.logical_sha256 == second_metadata.logical_sha256

    telemetry_root = first / "telemetry_events"
    telemetry = pl.read_parquet(telemetry_root / "part-000000.parquet")
    telemetry.tail(2).write_parquet(telemetry_root / "part-000000.parquet")
    telemetry.head(2).write_parquet(telemetry_root / "part-000001.parquet")
    assert logical_fixture_hash(first, schema) == second_metadata.logical_sha256
    assert logical_fixture_hash(first, schema) == logical_fixture_hash(second, schema)
