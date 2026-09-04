import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from portflow.pipeline import run_local_pipeline

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_seeded_pipeline_reconciles_public_snapshot(
    database_url: str,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "public" / "data"
    manifest_path = run_local_pipeline(database_url=database_url, output_dir=output_dir)
    manifest = read_json(manifest_path)

    assert manifest["datasets"].keys() == {
        "overview",
        "equipment",
        "incidents",
        "event_replay",
        "quality",
    }
    assert manifest["snapshot_id"] == "demo-v2"
    assert manifest["quality_status"] == "PASS"
    assert manifest["record_counts"] == {
        "telemetry": 288,
        "equipment": 1,
        "incidents": 2,
        "event_replay": 288,
        "quality": 1,
    }
    assert manifest["source_period_start"] == "2026-09-02T00:00:00Z"
    assert manifest["source_period_end"] == "2026-09-02T23:55:00Z"

    for entry in manifest["datasets"].values():
        dataset_path = output_dir / entry["path"]
        assert dataset_path.is_file()
        assert hashlib.sha256(dataset_path.read_bytes()).hexdigest() == entry["sha256"]

    overview = read_json(output_dir / manifest["datasets"]["overview"]["path"])
    equipment = read_json(output_dir / manifest["datasets"]["equipment"]["path"])
    incidents = read_json(output_dir / manifest["datasets"]["incidents"]["path"])
    replay = read_json(output_dir / manifest["datasets"]["event_replay"]["path"])
    quality = read_json(output_dir / manifest["datasets"]["quality"]["path"])

    assert overview["throughput"] == 4
    assert overview["active_incidents"] == 1
    assert overview["critical_alarms"] == 1
    assert equipment[0]["equipment_id"] == "QC-001"
    assert {incident["incident_id"] for incident in incidents} == {"inc-000001", "inc-000002"}
    assert len(replay) == 288
    assert quality["quarantine_rows"] == 0
    assert quality["bronze_rows"] == quality["silver_rows"]

    browser_environment = os.environ.copy()
    browser_environment["PORTFLOW_RECONCILIATION_DIR"] = str(output_dir)
    npm_command = "npm.cmd" if os.name == "nt" else "npm"
    browser_result = subprocess.run(
        [npm_command, "test", "--", "--run", "e2e/reconciliation.spec.tsx", "--pool=forks", "--maxWorkers=1"],
        cwd=Path(__file__).parents[2] / "web",
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=browser_environment,
    )
    assert browser_result.returncode == 0, (
        "browser reconciliation failed:\n"
        f"{browser_result.stdout}\n{browser_result.stderr}"
    )
