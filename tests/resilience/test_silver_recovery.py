from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from portflow.transforms.silver import SilverRunReport, transform_bronze_to_silver


def _telemetry(
    event_id: str,
    equipment_id: str,
    updated_at: datetime,
    *,
    load_percent: float = 50.0,
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "schema_version": 1,
        "equipment_id": equipment_id,
        "terminal_id": "TM-001",
        "event_timestamp": updated_at,
        "ingestion_timestamp": updated_at,
        "state": "ACTIVE",
        "available": True,
        "load_percent": load_percent,
        "temperature_c": 30.0,
        "created_at": updated_at,
        "updated_at": updated_at,
        "source_table": "telemetry_events",
        "extraction_run_id": "run-000042",
        "source_updated_at": updated_at,
        "extracted_at": updated_at + timedelta(seconds=2),
    }


def _write_fixture(root: Path, table_name: str, rows: list[dict[str, object]]) -> None:
    path = root / "bronze" / table_name / "date=2026-09-02" / "part.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(path)


def test_silver_quarantines_superseded_duplicate_with_stable_reason_code(
    tmp_path: Path,
) -> None:
    timestamp = datetime(2026, 9, 2, tzinfo=UTC)
    _write_fixture(
        tmp_path,
        "terminals",
        [
            {
                "terminal_id": "TM-001",
                "name": "Terminal 1",
                "timezone_name": "UTC",
                "created_at": timestamp,
                "updated_at": timestamp,
                "source_table": "terminals",
                "extraction_run_id": "run-000042",
                "source_updated_at": timestamp,
                "extracted_at": timestamp + timedelta(seconds=2),
            }
        ],
    )
    _write_fixture(
        tmp_path,
        "equipment",
        [
            {
                "equipment_id": "QC-001",
                "terminal_id": "TM-001",
                "equipment_type": "QUAY_CRANE",
                "commissioning_date": timestamp.date(),
                "created_at": timestamp,
                "updated_at": timestamp,
                "source_table": "equipment",
                "extraction_run_id": "run-000042",
                "source_updated_at": timestamp,
                "extracted_at": timestamp + timedelta(seconds=2),
            }
        ],
    )
    _write_fixture(
        tmp_path,
        "telemetry_events",
        [
            _telemetry("evt-000042-000001", "QC-001", timestamp),
            _telemetry(
                "evt-000042-000001",
                "QC-001",
                timestamp + timedelta(minutes=1),
                load_percent=75.0,
            ),
            _telemetry("evt-000042-000002", "QC-001", timestamp, load_percent=25.0),
        ],
    )

    report = transform_bronze_to_silver(
        bronze_dir=tmp_path / "bronze",
        silver_dir=tmp_path / "silver",
        quarantine_dir=tmp_path / "quarantine",
    )

    assert isinstance(report, SilverRunReport)
    assert report.quarantine_reason_counts == {"DUPLICATE_KEY": 1}
    assert report.bronze_rows == report.silver_rows + report.quarantine_rows
    silver_rows = pl.read_parquet(tmp_path / "silver" / "telemetry_events" / "part.parquet").to_dicts()
    assert {row["event_id"] for row in silver_rows} == {
        "evt-000042-000001",
        "evt-000042-000002",
    }
    newer_duplicate = next(row for row in silver_rows if row["event_id"] == "evt-000042-000001")
    assert newer_duplicate["load_percent"] == 75.0
    assert next(row for row in silver_rows if row["event_id"] == "evt-000042-000002")["load_percent"] == 25.0
    quarantine_rows = pl.read_parquet(tmp_path / "quarantine" / "telemetry_events" / "part.parquet").to_dicts()
    assert len(quarantine_rows) == 1
    assert quarantine_rows[0]["primary_key"] == "evt-000042-000001"
    assert quarantine_rows[0]["reason_codes"] == ["DUPLICATE_KEY"]
    assert '"load_percent":50.0' in quarantine_rows[0]["raw_payload"]


def test_silver_quarantines_invalid_reference_with_stable_reason_code(tmp_path: Path) -> None:
    timestamp = datetime(2026, 9, 2, tzinfo=UTC)
    _write_fixture(
        tmp_path,
        "terminals",
        [
            {
                "terminal_id": "TM-001",
                "name": "Terminal 1",
                "timezone_name": "UTC",
                "created_at": timestamp,
                "updated_at": timestamp,
                "source_table": "terminals",
                "extraction_run_id": "run-000042",
                "source_updated_at": timestamp,
                "extracted_at": timestamp + timedelta(seconds=2),
            }
        ],
    )
    _write_fixture(
        tmp_path,
        "telemetry_events",
        [
            _telemetry("evt-000042-000001", "QC-999", timestamp),
            _telemetry("evt-000042-000002", "QC-999", timestamp + timedelta(minutes=1)),
        ],
    )

    report = transform_bronze_to_silver(
        bronze_dir=tmp_path / "bronze",
        silver_dir=tmp_path / "silver",
        quarantine_dir=tmp_path / "quarantine",
    )

    assert report.quarantine_reason_counts == {"REFERENCE_INVALID": 2}
    assert report.bronze_rows == report.silver_rows + report.quarantine_rows
    assert not (tmp_path / "silver" / "telemetry_events" / "part.parquet").exists()
    quarantine_rows = pl.read_parquet(tmp_path / "quarantine" / "telemetry_events" / "part.parquet").to_dicts()
    assert {row["primary_key"] for row in quarantine_rows} == {
        "evt-000042-000001",
        "evt-000042-000002",
    }
    assert all(row["reason_codes"] == ["REFERENCE_INVALID"] for row in quarantine_rows)
