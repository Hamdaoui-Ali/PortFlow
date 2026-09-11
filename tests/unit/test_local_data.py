from datetime import UTC, datetime

import pytest

from portflow.ingestion.postgres_to_bronze import TABLE_SPECS
from portflow.local_data import (
    ImportValidationError,
    UnsupportedTableError,
    get_local_schema,
    normalize_records,
    validate_records,
)
from portflow.quality.rules import ReferenceSet

REFERENCES = ReferenceSet(
    terminal_ids=frozenset({"TM-001", "TM-101"}),
    equipment_ids=frozenset({"QC-001", "QC-101"}),
)


def telemetry_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "event_id": "evt-000042-000001",
        "schema_version": 1,
        "equipment_id": "QC-001",
        "terminal_id": "TM-001",
        "event_timestamp": "2026-09-02T00:00:00Z",
        "ingestion_timestamp": "2026-09-02T00:00:02Z",
        "state": "ACTIVE",
        "available": True,
        "load_percent": 50.0,
        "temperature_c": 55.0,
        "created_at": "2026-09-02T00:00:00Z",
        "updated_at": "2026-09-02T00:00:02Z",
    }
    row.update(overrides)
    return row


def alarm_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "alarm_id": "alm-000101",
        "equipment_id": "QC-001",
        "severity": "WARNING",
        "code": "TEMP_HIGH",
        "opened_at": "2026-09-02T01:00:00Z",
        "cleared_at": None,
        "created_at": "2026-09-02T01:00:00Z",
        "updated_at": "2026-09-02T01:00:00Z",
    }
    row.update(overrides)
    return row


def test_exposes_all_operational_tables() -> None:
    schemas = get_local_schema()

    assert [schema.table_name for schema in schemas] == list(TABLE_SPECS)
    assert all(
        tuple(column.name for column in schema.columns) == TABLE_SPECS[schema.table_name].columns
        for schema in schemas
    )


def test_normalizes_utc_datetime_and_date() -> None:
    record = {
        "terminal_id": "TM-101",
        "name": "Local Terminal",
        "timezone_name": "UTC",
        "created_at": "2026-09-02T00:00:00Z",
        "updated_at": "2026-09-02T00:00:02Z",
    }

    normalized = normalize_records("terminals", [record])[0]

    assert normalized["created_at"] == datetime(2026, 9, 2, tzinfo=UTC)
    assert normalized["created_at"].tzinfo == UTC

    equipment = normalize_records(
        "equipment",
        [{
            "equipment_id": "QC-101",
            "terminal_id": "TM-101",
            "equipment_type": "QUAY_CRANE",
            "commissioning_date": "2024-01-01",
            "created_at": "2026-09-02T00:00:00Z",
            "updated_at": "2026-09-02T00:00:02Z",
        }],
    )[0]
    assert equipment["commissioning_date"].isoformat() == "2024-01-01"


def test_rejects_unknown_table_and_unknown_field() -> None:
    with pytest.raises(UnsupportedTableError):
        normalize_records("not_a_source_table", [])

    with pytest.raises(ImportValidationError) as error:
        normalize_records(
            "terminals",
            [{
                "terminal_id": "TM-101",
                "name": "Local Terminal",
                "timezone_name": "UTC",
                "created_at": "2026-09-02T00:00:00Z",
                "updated_at": "2026-09-02T00:00:02Z",
                "unexpected": "reject me",
            }],
        )

    assert error.value.issues[0].field == "unexpected"
    assert error.value.issues[0].code == "SCHEMA_INVALID"


def test_reports_row_and_field_for_bad_telemetry_range() -> None:
    issues = validate_records(
        "telemetry_events",
        [telemetry_row(load_percent=101)],
        REFERENCES,
    )

    assert any(
        issue.row_index == 0
        and issue.field == "load_percent"
        and issue.code == "RANGE_INVALID"
        for issue in issues
    )


def test_reports_duplicate_primary_key_within_payload() -> None:
    row = telemetry_row()

    issues = validate_records("telemetry_events", [row, row], REFERENCES)

    assert any(
        issue.row_index == 1
        and issue.field == "event_id"
        and issue.code == "DUPLICATE_KEY"
        for issue in issues
    )


def test_reports_missing_required_field() -> None:
    row = telemetry_row()
    del row["temperature_c"]

    with pytest.raises(ImportValidationError) as error:
        normalize_records("telemetry_events", [row])

    assert any(issue.field == "temperature_c" for issue in error.value.issues)


def test_accepts_nullable_cleared_at() -> None:
    normalized = normalize_records("alarms", [alarm_row()])

    assert validate_records("alarms", normalized, REFERENCES) == []
