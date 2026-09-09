from pathlib import Path

import pytest
from scripts.check_budgets import (
    BudgetViolation,
    check_budgets,
    main,
    measure_bundle_bytes,
    measure_snapshot_bytes,
    measure_startup_bytes,
)


def test_snapshot_bytes_are_summed_recursively(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "data"
    (snapshot_root / "snapshots" / "demo-v2").mkdir(parents=True)
    (snapshot_root / "manifest.json").write_bytes(b"manifest")
    (snapshot_root / "snapshots" / "demo-v2" / "overview.json").write_bytes(b"overview")

    assert measure_snapshot_bytes(snapshot_root) == len(b"manifest") + len(b"overview")


def test_bundle_bytes_include_javascript_and_css_assets_only(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "index.js").write_bytes(b"js")
    (assets_dir / "index.css").write_bytes(b"css")
    (assets_dir / "font.woff2").write_bytes(b"font")
    (dist_dir / "index.html").write_bytes(b"html")

    assert measure_bundle_bytes(dist_dir) == len(b"js") + len(b"css")


@pytest.mark.parametrize("asset_prefix", ["/assets/", "/PortFlow/assets/"])
def test_startup_bytes_include_index_and_referenced_js_and_css(
    tmp_path: Path,
    asset_prefix: str,
) -> None:
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "index.js").write_bytes(b"js")
    (assets_dir / "index.css").write_bytes(b"css")
    (assets_dir / "unused.js").write_bytes(b"unused")
    (dist_dir / "index.html").write_text(
        f'<link rel="stylesheet" href="{asset_prefix}index.css">'
        f'<script type="module" src="{asset_prefix}index.js"></script>',
        encoding="utf-8",
    )

    expected = len((dist_dir / "index.html").read_bytes()) + len(b"js") + len(b"css")
    assert measure_startup_bytes(dist_dir) == expected


def test_check_budgets_reports_snapshot_overflow(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "data"
    snapshot_root.mkdir()
    (snapshot_root / "manifest.json").write_bytes(b"123456")
    dist_dir = tmp_path / "dist"
    (dist_dir / "assets").mkdir(parents=True)
    (dist_dir / "index.html").write_text("<main></main>", encoding="utf-8")

    assert check_budgets(
        snapshot_root,
        dist_dir,
        snapshot_limit=5,
        bundle_limit=100,
        startup_limit=100,
    ) == [BudgetViolation("snapshot", 6, 5)]


def test_main_returns_nonzero_and_reports_exceeded_budget(
    tmp_path: Path,
    capsys: object,
) -> None:
    snapshot_root = tmp_path / "data"
    snapshot_root.mkdir()
    (snapshot_root / "manifest.json").write_bytes(b"123456")
    dist_dir = tmp_path / "dist"
    (dist_dir / "assets").mkdir(parents=True)
    (dist_dir / "index.html").write_text("<main></main>", encoding="utf-8")

    exit_code = main(
        [
            "--snapshot-root",
            str(snapshot_root),
            "--dist-dir",
            str(dist_dir),
            "--snapshot-limit",
            "5",
            "--bundle-limit",
            "100",
            "--startup-limit",
            "100",
        ]
    )

    assert exit_code == 1
    assert "snapshot: 6 bytes (limit 5)" in capsys.readouterr().out  # type: ignore[attr-defined]
