import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from portflow.export.snapshot import write_first_snapshot
from portflow.simulator.equipment import generate_telemetry


def telemetry_events():
    return generate_telemetry(
        seed=42,
        equipment_id="QC-001",
        terminal_id="TM-001",
        count=20,
        start_at=datetime(2026, 9, 2, tzinfo=UTC),
    )


def test_snapshot_contains_version_hash_period_and_kpi(tmp_path: Path) -> None:
    """Catch an export that cannot be validated or reconciled by the browser."""
    manifest_path = write_first_snapshot(tmp_path, telemetry_events())
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    overview_path = tmp_path / manifest["datasets"]["overview"]["path"]
    overview_bytes = overview_path.read_bytes()
    overview = json.loads(overview_bytes)

    assert manifest["schema_version"] == 1
    assert manifest["snapshot_id"] == "demo-v1"
    assert manifest["generated_at"] == "2026-09-02T01:35:02Z"
    assert manifest["source_period_start"] == "2026-09-02T00:00:00Z"
    assert manifest["source_period_end"] == "2026-09-02T01:35:00Z"
    assert manifest["record_counts"] == {"telemetry": 20}
    assert manifest["datasets"]["overview"]["sha256"] == hashlib.sha256(
        overview_bytes
    ).hexdigest()
    assert overview["terminal_id"] == "TM-001"
    assert overview["availability"]["scheduled_intervals"] == 20
    assert overview["availability"]["value"] is not None


def test_repeated_export_produces_identical_bytes(tmp_path: Path) -> None:
    """Catch nondeterministic JSON ordering, timestamps, or hashes."""
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first_manifest = write_first_snapshot(first_root, telemetry_events())
    second_manifest = write_first_snapshot(second_root, telemetry_events())

    assert first_manifest.read_bytes() == second_manifest.read_bytes()
    assert (first_root / "snapshots/demo-v1/overview.json").read_bytes() == (
        second_root / "snapshots/demo-v1/overview.json"
    ).read_bytes()
