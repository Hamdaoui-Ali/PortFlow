"""Checksum-verified, idempotent SQL migration runner."""

import hashlib
from pathlib import Path

import psycopg


class MigrationChecksumError(ValueError):
    """Raised when an applied migration file changes."""


def apply_migrations(connection: psycopg.Connection, migrations_dir: Path) -> None:
    """Apply sorted SQL migrations once and verify previously applied checksums."""
    migration_paths = sorted(migrations_dir.glob("*.sql"))
    for migration_path in migration_paths:
        sql_bytes = migration_path.read_bytes()
        checksum = hashlib.sha256(sql_bytes).hexdigest()
        with connection.transaction():
            schema_table_row = connection.execute(
                "select to_regclass('public.schema_migrations')"
            ).fetchone()
            schema_table_exists = (
                schema_table_row is not None and schema_table_row[0] is not None
            )
            if schema_table_exists:
                existing = connection.execute(
                    "select checksum_sha256 from schema_migrations where filename = %s",
                    (migration_path.name,),
                ).fetchone()
                if existing is not None:
                    if existing[0] != checksum:
                        raise MigrationChecksumError(
                            f"migration checksum changed: {migration_path.name}"
                        )
                    continue

            connection.execute(sql_bytes.decode("utf-8"))
            connection.execute(
                """
                insert into schema_migrations (filename, checksum_sha256, applied_at)
                values (%s, %s, timezone('UTC', now()))
                on conflict (filename) do nothing
                """,
                (migration_path.name, checksum),
            )
