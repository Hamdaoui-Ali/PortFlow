from datetime import UTC, datetime, timedelta

from portflow.quality.rules import ReferenceSet


def valid_telemetry_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "event_id": "evt-000042-000001",
        "schema_version": 1,
        "equipment_id": "QC-001",
        "terminal_id": "TM-001",
        "event_timestamp": datetime(2026, 9, 2, tzinfo=UTC),
        "ingestion_timestamp": datetime(2026, 9, 2, 0, 0, 2, tzinfo=UTC),
        "state": "ACTIVE",
        "available": True,
        "load_percent": 50.0,
        "temperature_c": 55.0,
        "created_at": datetime(2026, 9, 2, tzinfo=UTC),
        "updated_at": datetime(2026, 9, 2, 0, 0, 2, tzinfo=UTC),
        "source_table": "telemetry_events",
        "extraction_run_id": "run-000042",
        "source_updated_at": datetime(2026, 9, 2, 0, 0, 2, tzinfo=UTC),
        "extracted_at": datetime(2026, 9, 2, 0, 0, 4, tzinfo=UTC),
    }
    row.update(overrides)
    return row


def references() -> ReferenceSet:
    return ReferenceSet(
        terminal_ids=frozenset({"TM-001"}),
        equipment_ids=frozenset({"QC-001"}),
    )
