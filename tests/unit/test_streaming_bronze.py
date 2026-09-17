from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from portflow.domain.models import EquipmentState, TelemetryEvent
from portflow.ingestion.postgres_to_bronze import (
    TABLE_SPECS,
    write_telemetry_bronze_batch,
)


def event(event_id: str, offset_minutes: int) -> TelemetryEvent:
    start = datetime(2026, 9, 2, tzinfo=UTC) + timedelta(minutes=offset_minutes)
    return TelemetryEvent(
        event_id=event_id,
        schema_version=1,
        equipment_id="QC-001",
        terminal_id="TM-001",
        event_timestamp=start,
        ingestion_timestamp=start + timedelta(seconds=2),
        state=EquipmentState.ACTIVE,
        available=True,
        load_percent=50.0,
        temperature_c=55.0,
    )


def test_stream_batch_matches_existing_telemetry_bronze_contract(tmp_path: Path) -> None:
    events = [event("evt-000042-000001", 0), event("evt-000042-000002", 5)]

    result = write_telemetry_bronze_batch(
        list(reversed(events)),
        bronze_dir=tmp_path / "bronze",
        run_id="stream-run-000042",
    )
    frame = pl.read_parquet(result.partition_path)

    assert result.table_name == "telemetry_events"
    assert result.row_count == 2
    assert frame.columns == [
        *TABLE_SPECS["telemetry_events"].columns,
        "source_table",
        "extraction_run_id",
        "source_updated_at",
        "extracted_at",
    ]
    assert frame["event_id"].to_list() == [
        "evt-000042-000001",
        "evt-000042-000002",
    ]
    assert frame["source_table"].unique().to_list() == ["telemetry_events"]
    assert frame["extraction_run_id"].unique().to_list() == ["stream-run-000042"]


def test_reversed_input_reuses_the_same_partition_hash(tmp_path: Path) -> None:
    events = [event("evt-000042-000001", 0), event("evt-000042-000002", 5)]

    first = write_telemetry_bronze_batch(
        events,
        bronze_dir=tmp_path / "first",
        run_id="stream-run-000042",
    )
    second = write_telemetry_bronze_batch(
        list(reversed(events)),
        bronze_dir=tmp_path / "second",
        run_id="stream-run-000042",
    )

    assert first.content_sha256 == second.content_sha256
    assert first.partition_path.read_bytes() == second.partition_path.read_bytes()


@pytest.mark.parametrize(
    "events, run_id",
    [([], "stream-run-000042"), ([event("evt-000042-000001", 0)], "")],
)
def test_rejects_empty_events_and_run_id(
    tmp_path: Path,
    events: list[TelemetryEvent],
    run_id: str,
) -> None:
    with pytest.raises(ValueError):
        write_telemetry_bronze_batch(
            events,
            bronze_dir=tmp_path / "bronze",
            run_id=run_id,
        )

    assert not list((tmp_path / "bronze").rglob("*.parquet"))


def test_rejects_whitespace_run_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="run_id"):
        write_telemetry_bronze_batch(
            [event("evt-000042-000001", 0)],
            bronze_dir=tmp_path / "bronze",
            run_id="   ",
        )

    assert not list((tmp_path / "bronze").rglob("*.parquet"))
