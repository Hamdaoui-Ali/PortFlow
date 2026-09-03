from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest

from portflow.db.migrations import apply_migrations


def test_migrations_are_idempotent(database_url: str, migrations_dir: Path) -> None:
    with psycopg.connect(database_url) as connection:
        apply_migrations(connection, migrations_dir)
        apply_migrations(connection, migrations_dir)
        count = connection.execute(
            "select count(*) from schema_migrations"
        ).fetchone()[0]
    assert count == 1


def test_migration_checksum_is_line_ending_invariant(
    database_url: str, migrations_dir: Path, tmp_path: Path
) -> None:
    source_path = migrations_dir / "001_operational_schema.sql"
    source_bytes = source_path.read_bytes()
    if b"\r\n" in source_bytes:
        alternate_bytes = source_bytes.replace(b"\r\n", b"\n")
    else:
        alternate_bytes = source_bytes.replace(b"\n", b"\r\n")

    alternate_dir = tmp_path / "migrations"
    alternate_dir.mkdir()
    (alternate_dir / source_path.name).write_bytes(alternate_bytes)

    with psycopg.connect(database_url) as connection:
        apply_migrations(connection, migrations_dir)
        apply_migrations(connection, alternate_dir)


def test_foreign_key_and_value_checks_reject_invalid_rows(database_url: str) -> None:
    with psycopg.connect(database_url) as connection:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            connection.execute(
                """
                insert into equipment
                    (equipment_id, terminal_id, equipment_type, commissioning_date,
                     created_at, updated_at)
                values ('QC-999', 'TM-999', 'QUAY_CRANE', %s, %s, %s)
                """,
                (datetime(2026, 1, 1, tzinfo=UTC),) * 3,
            )
        connection.rollback()
        with pytest.raises(psycopg.errors.CheckViolation):
            connection.execute(
                """
                insert into terminals
                    (terminal_id, name, timezone_name, created_at, updated_at)
                values ('TM-999', 'Bad terminal', 'UTC', %s, %s)
                """,
                (datetime(2026, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC)),
            )
