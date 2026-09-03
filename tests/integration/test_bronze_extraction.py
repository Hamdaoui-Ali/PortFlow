from pathlib import Path

import psycopg
import pytest

from portflow.db.migrations import apply_migrations
from portflow.ingestion.cursor import CursorStore, read_cursor
from portflow.ingestion.postgres_to_bronze import ExtractionResult, extract_table
from portflow.seed import SeedReport, seed_operational


def seed_database(database_url: str) -> SeedReport:
    migrations_dir = Path(__file__).parents[2] / "db" / "migrations"
    with psycopg.connect(database_url) as connection:
        apply_migrations(connection, migrations_dir)
        return seed_operational(connection, seed=42)


def extract_table_for_test(
    database_url: str,
    root: Path,
    *,
    batch_size: int = 1000,
) -> ExtractionResult:
    with psycopg.connect(database_url) as connection:
        return extract_table(
            connection,
            table_name="telemetry_events",
            cursor_store=CursorStore(root / "state" / "cursors.json"),
            bronze_dir=root / "bronze",
            run_id="run-000042",
            batch_size=batch_size,
        )


def fail_once_with_os_error(path: Path, target: Path) -> None:
    raise OSError(f"disk full while moving {path} to {target}")


def test_extraction_handles_ties_and_is_logically_idempotent(
    database_url: str,
    tmp_path: Path,
) -> None:
    seed_database(database_url)
    first = extract_table_for_test(database_url, tmp_path, batch_size=37)
    second = extract_table_for_test(database_url, tmp_path, batch_size=37)
    assert first.logical_row_count == 288
    assert second.logical_row_count == 288
    assert first.content_sha256 == second.content_sha256


def test_failed_partition_does_not_advance_cursor(
    database_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_database(database_url)
    monkeypatch.setattr(Path, "replace", fail_once_with_os_error)
    with pytest.raises(OSError):
        extract_table_for_test(database_url, tmp_path)
    assert read_cursor(tmp_path / "state" / "cursors.json", "telemetry_events") is None
    assert not list((tmp_path / "bronze").rglob("*.parquet"))
