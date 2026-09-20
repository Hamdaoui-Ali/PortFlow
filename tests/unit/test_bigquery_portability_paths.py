from pathlib import Path

import pytest

from labs.portflow_bigquery.paths import (
    ArtifactPathError,
    resolve_artifact_path,
    resolve_artifact_root,
)


def test_default_root_is_below_repository_portability_directory(tmp_path: Path) -> None:
    assert resolve_artifact_root(repository_root=tmp_path) == (
        tmp_path / ".portability" / "bigquery"
    ).resolve()


def test_explicit_root_must_remain_below_repository_portability_directory(
    tmp_path: Path,
) -> None:
    with pytest.raises(ArtifactPathError, match="artifact root"):
        resolve_artifact_root(tmp_path / "outside", repository_root=tmp_path)


@pytest.mark.parametrize("relative_path", ["../escape.json", "..\\escape.json", "/tmp/escape.json"])
def test_child_path_rejects_traversal_and_absolute_paths(
    tmp_path: Path,
    relative_path: str,
) -> None:
    root = resolve_artifact_root(repository_root=tmp_path)

    with pytest.raises(ArtifactPathError, match="artifact path"):
        resolve_artifact_path(root, relative_path)


def test_child_path_resolves_inside_root(tmp_path: Path) -> None:
    root = resolve_artifact_root(repository_root=tmp_path)

    assert resolve_artifact_path(root, "manifest.json") == (root / "manifest.json").resolve()
