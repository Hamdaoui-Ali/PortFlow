import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from portflow.export.models import PublicSnapshotMetadata
from portflow.export.writer import ExportValidationError, write_public_snapshot
from tests.integration.test_gold import prepare_silver, run_dbt


def source_metadata() -> PublicSnapshotMetadata:
    return PublicSnapshotMetadata(
        snapshot_id="demo-v2",
        generated_at=datetime(2026, 9, 2, 23, 55, 2, tzinfo=UTC),
        source_period_start=datetime(2026, 9, 2, tzinfo=UTC),
        source_period_end=datetime(2026, 9, 2, 23, 55, tzinfo=UTC),
    )


@pytest.fixture
def gold_db(database_url: str, tmp_path: Path) -> Path:
    silver_dir = prepare_silver(database_url, tmp_path)
    gold_db_path = tmp_path / "gold" / "portflow.duckdb"
    result = run_dbt(silver_dir, gold_db_path)
    assert result.returncode == 0, f"dbt failed:\n{result.stdout}\n{result.stderr}"
    return gold_db_path


def corrupt_gold_db(gold_db: Path, *, overview_availability: float) -> None:
    with duckdb.connect(str(gold_db)) as connection:
        connection.execute(
            "update overview_kpis set availability = ?",
            [overview_availability],
        )


def test_export_contains_all_datasets_and_verified_hashes(
    tmp_path: Path,
    gold_db: Path,
) -> None:
    manifest_path = write_public_snapshot(
        output_dir=tmp_path / "public" / "data",
        gold_db=gold_db,
        source_metadata=source_metadata(),
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {"overview", "equipment", "incidents", "event_replay", "quality"}
    assert set(manifest["datasets"]) == required
    for entry in manifest["datasets"].values():
        dataset = (manifest_path.parent / entry["path"]).read_bytes()
        assert hashlib.sha256(dataset).hexdigest() == entry["sha256"]
    assert manifest["quality_status"] == "PASS"


def test_repeated_export_accepts_line_ending_variants(
    tmp_path: Path,
    gold_db: Path,
) -> None:
    output_dir = tmp_path / "public" / "data"
    write_public_snapshot(output_dir, gold_db, source_metadata())
    snapshot_dir = output_dir / "snapshots" / "demo-v2"
    for dataset_path in snapshot_dir.glob("*.json"):
        dataset_path.write_bytes(dataset_path.read_bytes().replace(b"\n", b"\r\n"))

    write_public_snapshot(output_dir, gold_db, source_metadata())


def test_export_rejects_gold_export_mismatch(tmp_path: Path, gold_db: Path) -> None:
    corrupt_gold_db(gold_db, overview_availability=0.1)
    with pytest.raises(ExportValidationError, match="Gold-to-export reconciliation"):
        write_public_snapshot(tmp_path / "public" / "data", gold_db, source_metadata())
    assert not (tmp_path / "public" / "data" / "manifest.json").exists()
