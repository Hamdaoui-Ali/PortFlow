import hashlib
import json
from pathlib import Path

import pytest
from tests.integration.test_public_export import source_metadata

import portflow.export.writer as writer
from portflow.export.writer import ExportValidationError, write_public_snapshot


def test_failed_second_export_preserves_published_snapshot(
    tmp_path: Path,
    gold_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "public" / "data"
    manifest_path = write_public_snapshot(output_dir, gold_db, source_metadata())
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    dataset_bytes = {
        name: (manifest_path.parent / entry["path"]).read_bytes()
        for name, entry in manifest["datasets"].items()
    }

    def fail_write(path: Path, payload: bytes) -> None:
        raise OSError("simulated snapshot write failure")

    monkeypatch.setattr(writer, "_write_bytes", fail_write)
    with pytest.raises(ExportValidationError, match="simulated snapshot write failure"):
        write_public_snapshot(output_dir, gold_db, source_metadata())

    assert manifest_path.read_bytes() == manifest_bytes
    for name, expected in dataset_bytes.items():
        assert (manifest_path.parent / manifest["datasets"][name]["path"]).read_bytes() == expected
        assert hashlib.sha256(expected).hexdigest() == manifest["datasets"][name]["sha256"]
    assert not (output_dir / ".staging" / "demo-v2").exists()
