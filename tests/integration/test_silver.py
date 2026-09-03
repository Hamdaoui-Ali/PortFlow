from datetime import timedelta
from pathlib import Path

import polars as pl
import psycopg

from portflow.db.migrations import apply_migrations
from portflow.ingestion.cursor import CursorStore
from portflow.ingestion.postgres_to_bronze import extract_table
from portflow.seed import SeedReport, seed_operational
from portflow.transforms.silver import SilverRunReport, transform_bronze_to_silver


def seed_database(database_url: str) -> SeedReport:
    migrations_dir = Path(__file__).parents[2] / "db" / "migrations"
    with psycopg.connect(database_url) as connection:
        apply_migrations(connection, migrations_dir)
        return seed_operational(connection, seed=42)


def extract_reference_and_telemetry_tables(database_url: str, root: Path) -> None:
    with psycopg.connect(database_url) as connection:
        for table_name in ("terminals", "equipment", "telemetry_events"):
            extract_table(
                connection,
                table_name=table_name,
                cursor_store=CursorStore(root / "state" / f"{table_name}.json"),
                bronze_dir=root / "bronze",
                run_id="run-000042",
            )


def append_invalid_bronze_fixture(
    root: Path,
    *,
    missing_reference: bool,
    bad_range: bool,
) -> None:
    source_path = next((root / "bronze" / "telemetry_events").rglob("*.parquet"))
    base = pl.read_parquet(source_path).to_dicts()[0]
    rows: list[dict[str, object]] = []
    if missing_reference:
        row = dict(base)
        row.update(
            {
                "event_id": "evt-000042-100001",
                "equipment_id": "QC-999",
                "source_updated_at": base["source_updated_at"] + timedelta(hours=1),
                "updated_at": base["updated_at"] + timedelta(hours=1),
            }
        )
        rows.append(row)
    if bad_range:
        row = dict(base)
        row.update(
            {
                "event_id": "evt-000042-100002",
                "load_percent": 101.0,
                "source_updated_at": base["source_updated_at"] + timedelta(hours=2),
                "updated_at": base["updated_at"] + timedelta(hours=2),
            }
        )
        rows.append(row)
    output = root / "bronze" / "telemetry_events" / "date=2026-09-02" / "part-invalid.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(output)


def test_silver_reconciles_accepted_and_quarantined_rows(
    database_url: str,
    tmp_path: Path,
) -> None:
    seed_database(database_url)
    extract_reference_and_telemetry_tables(database_url, tmp_path)
    append_invalid_bronze_fixture(tmp_path, missing_reference=True, bad_range=True)
    report = transform_bronze_to_silver(
        bronze_dir=tmp_path / "bronze",
        silver_dir=tmp_path / "silver",
        quarantine_dir=tmp_path / "quarantine",
    )
    assert isinstance(report, SilverRunReport)
    assert report.bronze_rows == report.silver_rows + report.quarantine_rows
    assert report.quarantine_reason_counts == {"RANGE_INVALID": 1, "REFERENCE_MISSING": 1}
    quarantine_path = next((tmp_path / "quarantine").rglob("*.parquet"))
    quarantine_rows = pl.read_parquet(quarantine_path).to_dicts()
    assert all(row["raw_payload"] for row in quarantine_rows)
    assert {code for row in quarantine_rows for code in row["reason_codes"]} == {
        "RANGE_INVALID",
        "REFERENCE_MISSING",
    }
