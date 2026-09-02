"""End-to-end local pipeline from PostgreSQL to the static public snapshot."""

import os
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from portflow.db.connection import get_connection
from portflow.db.migrations import apply_migrations
from portflow.export.models import PublicSnapshotMetadata
from portflow.export.writer import write_public_snapshot
from portflow.ingestion.cursor import CursorStore
from portflow.ingestion.postgres_to_bronze import TABLE_SPECS, extract_table
from portflow.seed import seed_operational
from portflow.transforms.silver import transform_bronze_to_silver


class PipelineError(RuntimeError):
    """Raised when a local pipeline stage fails before public export."""


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_dbt(*, silver_dir: Path, gold_db: Path) -> None:
    repository_root = _repository_root()
    gold_db.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["PORTFLOW_SILVER_DIR"] = silver_dir.as_posix()
    environment["PORTFLOW_GOLD_DB"] = gold_db.as_posix()
    result = subprocess.run(
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
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise PipelineError(f"dbt build failed: {detail}")


def run_local_pipeline(
    *,
    database_url: str,
    output_dir: Path,
    seed: int = 42,
) -> Path:
    """Run migrations, seed, Bronze, Silver, Gold, and atomic public export."""
    repository_root = _repository_root()
    source_start = datetime(2026, 9, 2, tzinfo=UTC)
    source_end = source_start + timedelta(minutes=5 * 287)
    generated_at = source_end + timedelta(seconds=2)

    with tempfile.TemporaryDirectory(prefix="portflow-pipeline-") as temporary_root:
        work_dir = Path(temporary_root)
        bronze_dir = work_dir / "bronze"
        silver_dir = work_dir / "silver"
        quarantine_dir = work_dir / "quarantine"
        cursor_store = CursorStore(work_dir / "state" / "cursors.json")

        try:
            with get_connection(database_url) as connection:
                apply_migrations(connection, repository_root / "db" / "migrations")
                seed_operational(connection, seed=seed)
                for table_name in TABLE_SPECS:
                    extract_table(
                        connection,
                        table_name=table_name,
                        cursor_store=cursor_store,
                        bronze_dir=bronze_dir,
                        run_id=f"run-{seed:06d}",
                    )
        except Exception as error:
            raise PipelineError(f"source stage failed: {error}") from error

        try:
            quality_report = transform_bronze_to_silver(
                bronze_dir=bronze_dir,
                silver_dir=silver_dir,
                quarantine_dir=quarantine_dir,
            )
            if (
                quality_report.bronze_rows
                != quality_report.silver_rows + quality_report.quarantine_rows
            ):
                raise PipelineError("Silver reconciliation failed")
            gold_db = work_dir / "gold" / "portflow.duckdb"
            _run_dbt(silver_dir=silver_dir, gold_db=gold_db)
            return write_public_snapshot(
                output_dir=output_dir,
                gold_db=gold_db,
                source_metadata=PublicSnapshotMetadata(
                    snapshot_id="demo-v2",
                    generated_at=generated_at,
                    source_period_start=source_start,
                    source_period_end=source_end,
                ),
            )
        except PipelineError:
            raise
        except Exception as error:
            raise PipelineError(f"analytics or export stage failed: {error}") from error
