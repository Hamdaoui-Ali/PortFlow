from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest

from portflow.db.migrations import apply_migrations
from portflow.ingestion.cursor import CursorStore, SourceCursor, read_cursor
from portflow.ingestion.postgres_to_bronze import extract_table
from portflow.seed import seed_operational


def test_cursor_replacement_failure_preserves_previous_file(tmp_path: Path) -> None:
    path = tmp_path / "state" / "cursors.json"
    store = CursorStore(path)
    previous = SourceCursor(datetime(2026, 9, 2, tzinfo=UTC), "row-001")
    store.save({"telemetry_events": previous})

    def fail_replace(*args: object, **kwargs: object) -> None:
        raise OSError("simulated cursor replacement failure")

    with pytest.raises(OSError, match="simulated cursor replacement failure"):
        store.save(
            {
                "telemetry_events": SourceCursor(
                    datetime(2026, 9, 2, 0, 5, tzinfo=UTC), "row-002"
                )
            },
            replace=fail_replace,
        )

    assert store.load() == {"telemetry_events": previous}
    assert path.with_name("cursors.json.tmp").exists() is False


def test_extraction_failure_does_not_commit_partition_or_cursor(
    database_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migrations_dir = Path(__file__).parents[2] / "db" / "migrations"
    with psycopg.connect(database_url) as connection:
        apply_migrations(connection, migrations_dir)
        seed_operational(connection, seed=42)

        def fail_replace(path: Path, target: Path) -> None:
            raise OSError(f"disk full while moving {path} to {target}")

        monkeypatch.setattr(Path, "replace", fail_replace)
        with pytest.raises(OSError):
            extract_table(
                connection,
                table_name="telemetry_events",
                cursor_store=CursorStore(tmp_path / "state" / "cursors.json"),
                bronze_dir=tmp_path / "bronze",
                run_id="run-000042",
            )

    assert read_cursor(tmp_path / "state" / "cursors.json", "telemetry_events") is None
    assert not list((tmp_path / "bronze").rglob("*.parquet"))
