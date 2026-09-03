import os
import subprocess
from pathlib import Path

import duckdb
import psycopg

from portflow.db.migrations import apply_migrations
from portflow.ingestion.cursor import CursorStore
from portflow.ingestion.postgres_to_bronze import TABLE_SPECS, extract_table
from portflow.seed import seed_operational
from portflow.transforms.silver import transform_bronze_to_silver


def prepare_silver(database_url: str, root: Path) -> Path:
    migrations_dir = Path(__file__).parents[2] / "db" / "migrations"
    with psycopg.connect(database_url) as connection:
        apply_migrations(connection, migrations_dir)
        seed_operational(connection, seed=42)
        cursor_store = CursorStore(root / "state" / "cursors.json")
        for table_name in TABLE_SPECS:
            extract_table(
                connection,
                table_name=table_name,
                cursor_store=cursor_store,
                bronze_dir=root / "bronze",
                run_id="run-000042",
            )
    transform_bronze_to_silver(
        bronze_dir=root / "bronze",
        silver_dir=root / "silver",
        quarantine_dir=root / "quarantine",
    )
    return root / "silver"


def run_dbt(silver_dir: Path, gold_db: Path) -> subprocess.CompletedProcess[str]:
    repository_root = Path(__file__).parents[2]
    gold_db.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["PORTFLOW_SILVER_DIR"] = silver_dir.as_posix()
    environment["PORTFLOW_GOLD_DB"] = gold_db.as_posix()
    return subprocess.run(
        [
            "dbt",
            "build",
            "--project-dir",
            str(repository_root / "analytics"),
            "--profiles-dir",
            str(repository_root / "analytics"),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_dbt_builds_gold_models_and_reconciles_counts(
    database_url: str,
    tmp_path: Path,
) -> None:
    silver_dir = prepare_silver(database_url, tmp_path)
    gold_db = tmp_path / "gold" / "portflow.duckdb"
    result = run_dbt(silver_dir, gold_db)
    assert result.returncode == 0, f"dbt failed:\n{result.stdout}\n{result.stderr}"

    with duckdb.connect(str(gold_db), read_only=True) as connection:
        telemetry_count = connection.execute(
            "select count(*) from fct_equipment_telemetry"
        ).fetchone()[0]
        incident_count = connection.execute("select count(*) from fct_incidents").fetchone()[0]
        movement_count = connection.execute("select count(*) from fct_movements").fetchone()[0]
        overview = connection.execute(
            "select throughput, active_incidents, critical_alarms from overview_kpis"
        ).fetchone()
    assert telemetry_count == 288
    assert incident_count == 2
    assert movement_count == 8
    assert overview == (4, 1, 1)
