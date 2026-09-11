from datetime import UTC, datetime

import psycopg
import pytest

from portflow.db.migrations import apply_migrations
from portflow.local_data import ImportValidationError, import_records

TERMINAL_ROW = {
    "terminal_id": "TM-101",
    "name": "Local Test Terminal",
    "timezone_name": "UTC",
    "created_at": datetime(2026, 9, 2, tzinfo=UTC),
    "updated_at": datetime(2026, 9, 2, 0, 0, 2, tzinfo=UTC),
}
EQUIPMENT_ROW = {
    "equipment_id": "QC-101",
    "terminal_id": "TM-101",
    "equipment_type": "QUAY_CRANE",
    "commissioning_date": "2024-01-01",
    "created_at": "2026-09-02T00:00:00Z",
    "updated_at": "2026-09-02T00:00:02Z",
}
INCIDENT_ROW = {
    "incident_id": "inc-000101",
    "equipment_id": "QC-101",
    "severity": "MAJOR",
    "status": "OPEN",
    "opened_at": "2026-09-02T12:00:00Z",
    "resolved_at": None,
    "root_cause": "Hydraulic leak",
    "created_at": "2026-09-02T12:00:00Z",
    "updated_at": "2026-09-02T12:00:00Z",
}


def test_import_inserts_then_updates_by_primary_key(database_url: str, migrations_dir) -> None:
    with psycopg.connect(database_url) as connection:
        apply_migrations(connection, migrations_dir)
        first = import_records(connection, table_name="terminals", records=[TERMINAL_ROW])
        assert first.received_count == 1
        assert first.inserted_count == 1
        assert first.updated_count == 0

        changed_terminal = {**TERMINAL_ROW, "name": "Updated local terminal"}
        second = import_records(
            connection,
            table_name="terminals",
            records=[changed_terminal],
        )
        assert second.inserted_count == 0
        assert second.updated_count == 1

        with connection.cursor() as cursor:
            cursor.execute(
                "select name from terminals where terminal_id = %s",
                ("TM-101",),
            )
            assert cursor.fetchone()[0] == "Updated local terminal"


def test_import_rejects_missing_foreign_reference_without_writing(
    database_url: str,
    migrations_dir,
) -> None:
    with psycopg.connect(database_url) as connection:
        apply_migrations(connection, migrations_dir)
        with pytest.raises(ImportValidationError) as error:
            import_records(
                connection,
                table_name="equipment",
                records=[{**EQUIPMENT_ROW, "terminal_id": "TM-999"}],
            )

        assert error.value.issues[0].code == "REFERENCE_INVALID"
        with connection.cursor() as cursor:
            cursor.execute("select count(*) from equipment")
            assert cursor.fetchone()[0] == 0


def test_import_rejects_an_invalid_batch_without_partial_write(
    database_url: str,
    migrations_dir,
) -> None:
    with psycopg.connect(database_url) as connection:
        apply_migrations(connection, migrations_dir)
        import_records(connection, table_name="terminals", records=[TERMINAL_ROW])

        invalid_equipment = {
            **EQUIPMENT_ROW,
            "equipment_id": "QC-102",
            "terminal_id": "TM-999",
        }
        with pytest.raises(ImportValidationError):
            import_records(
                connection,
                table_name="equipment",
                records=[EQUIPMENT_ROW, invalid_equipment],
            )

        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from equipment where equipment_id in (%s, %s)",
                ("QC-101", "QC-102"),
            )
            assert cursor.fetchone()[0] == 0
