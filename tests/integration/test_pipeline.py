import hashlib
import json
from pathlib import Path

from portflow.pipeline import run_local_pipeline


def test_local_pipeline_publishes_an_idempotent_complete_snapshot(
    database_url: str,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "public" / "data"
    first_manifest_path = run_local_pipeline(
        database_url=database_url,
        output_dir=output_dir,
    )
    first_manifest = first_manifest_path.read_bytes()
    second_manifest_path = run_local_pipeline(
        database_url=database_url,
        output_dir=output_dir,
    )
    assert first_manifest == second_manifest_path.read_bytes()

    manifest = json.loads(first_manifest)
    assert set(manifest["datasets"]) == {
        "overview",
        "equipment",
        "incidents",
        "event_replay",
        "quality",
    }
    for entry in manifest["datasets"].values():
        dataset_path = output_dir / entry["path"]
        assert hashlib.sha256(dataset_path.read_bytes()).hexdigest() == entry["sha256"]
