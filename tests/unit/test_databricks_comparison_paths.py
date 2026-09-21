from pathlib import Path

import pytest
from labs.portflow_databricks.paths import (
    ArtifactPathError,
    DEFAULT_COMPARISON_ROOT,
    resolve_comparison_path,
    resolve_comparison_root,
)


def test_comparison_root_is_below_databricks_root(tmp_path: Path) -> None:
    root = resolve_comparison_root(repository_root=tmp_path)
    assert DEFAULT_COMPARISON_ROOT == Path(".databricks") / "pf108"
    assert root == (tmp_path / ".databricks" / "pf108").resolve()


@pytest.mark.parametrize(
    "value",
    ["../escape.json", r"..\escape.json", "/tmp/result.json", r"C:\tmp\result.json"],
)
def test_comparison_paths_reject_cross_platform_escape(tmp_path: Path, value: str) -> None:
    root = resolve_comparison_root(repository_root=tmp_path)
    with pytest.raises(ArtifactPathError, match="artifact path"):
        resolve_comparison_path(root, value)


def test_comparison_paths_reject_reparse_components(tmp_path: Path) -> None:
    root = resolve_comparison_root(repository_root=tmp_path)
    root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory links unavailable: {error}")
    with pytest.raises(ArtifactPathError, match="reparse"):
        resolve_comparison_path(root, "linked/result.json")
