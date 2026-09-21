from pathlib import Path

import pytest
from labs.portflow_databricks.paths import (
    ArtifactPathError,
    resolve_artifact_path,
    resolve_artifact_root,
)


def test_artifact_paths_reject_cross_platform_escape(tmp_path: Path) -> None:
    root = resolve_artifact_root(repository_root=tmp_path)
    for value in (
        "../escape.json",
        r"..\escape.json",
        "/tmp/escape.json",
        r"C:\tmp\escape.json",
        "nested/./escape.json",
    ):
        with pytest.raises(ArtifactPathError, match="artifact path"):
            resolve_artifact_path(root, value)


def test_artifact_paths_reject_reparse_components(tmp_path: Path) -> None:
    root = resolve_artifact_root(repository_root=tmp_path)
    root.mkdir(parents=True)
    target = tmp_path / "outside"
    target.mkdir()
    link = root / "linked"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory links unavailable: {error}")
    with pytest.raises(ArtifactPathError, match="reparse"):
        resolve_artifact_path(root, "linked/result.json")
