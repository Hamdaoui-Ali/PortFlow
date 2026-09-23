"""Measure and enforce PortFlow's committed data and build budgets."""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

SNAPSHOT_BUDGET_BYTES = 100_000
# PF-118 adds the bounded Overview incident pulse while keeping the measured
# bundle increase below one kilobyte of the previous guardrail.
BUNDLE_BUDGET_BYTES = 401_000
STARTUP_BUDGET_BYTES = 400_000


@dataclass(frozen=True)
class BudgetViolation:
    name: str
    actual_bytes: int
    limit_bytes: int


class _StartupAssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("src"):
            self.references.add(attributes["src"] or "")
        if tag == "link" and attributes.get("rel") == "stylesheet" and attributes.get("href"):
            self.references.add(attributes["href"] or "")


def _asset_path(dist_dir: Path, reference: str) -> Path:
    path = urlsplit(reference).path
    marker = "/assets/"
    if marker in path:
        relative = Path("assets") / Path(path.split(marker, 1)[1])
    else:
        relative = Path(path.lstrip("/"))
    candidate = (dist_dir / relative).resolve()
    candidate.relative_to(dist_dir.resolve())
    return candidate


def measure_snapshot_bytes(snapshot_root: Path) -> int:
    """Return the byte size of every file below a public data root."""
    return sum(path.stat().st_size for path in snapshot_root.rglob("*") if path.is_file())


def measure_bundle_bytes(dist_dir: Path) -> int:
    """Return the byte size of built JavaScript and CSS assets."""
    assets_dir = dist_dir / "assets"
    return sum(
        path.stat().st_size
        for path in assets_dir.rglob("*")
        if path.is_file() and path.suffix in {".css", ".js"}
    )


def measure_startup_bytes(dist_dir: Path) -> int:
    """Return index.html plus its local JavaScript and CSS references."""
    index_path = dist_dir / "index.html"
    parser = _StartupAssetParser()
    parser.feed(index_path.read_text(encoding="utf-8"))
    paths = {index_path}
    paths.update(_asset_path(dist_dir, reference) for reference in parser.references)
    return sum(path.stat().st_size for path in paths)


def check_budgets(
    snapshot_root: Path,
    dist_dir: Path,
    *,
    snapshot_limit: int = SNAPSHOT_BUDGET_BYTES,
    bundle_limit: int = BUNDLE_BUDGET_BYTES,
    startup_limit: int = STARTUP_BUDGET_BYTES,
) -> list[BudgetViolation]:
    """Return every byte budget exceeded by the supplied public build."""
    measurements = _measurements(
        snapshot_root,
        dist_dir,
        snapshot_limit=snapshot_limit,
        bundle_limit=bundle_limit,
        startup_limit=startup_limit,
    )
    return [
        BudgetViolation(name, actual, limit)
        for name, actual, limit in measurements
        if actual > limit
    ]


def _measurements(
    snapshot_root: Path,
    dist_dir: Path,
    *,
    snapshot_limit: int,
    bundle_limit: int,
    startup_limit: int,
) -> tuple[tuple[str, int, int], ...]:
    return (
        ("snapshot", measure_snapshot_bytes(snapshot_root), snapshot_limit),
        ("bundle", measure_bundle_bytes(dist_dir), bundle_limit),
        ("startup", measure_startup_bytes(dist_dir), startup_limit),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-root", type=Path, default=Path("web/public/data"))
    parser.add_argument("--dist-dir", type=Path, default=Path("web/dist"))
    parser.add_argument("--snapshot-limit", type=int, default=SNAPSHOT_BUDGET_BYTES)
    parser.add_argument("--bundle-limit", type=int, default=BUNDLE_BUDGET_BYTES)
    parser.add_argument("--startup-limit", type=int, default=STARTUP_BUDGET_BYTES)
    args = parser.parse_args(argv)

    measurements = _measurements(
        args.snapshot_root,
        args.dist_dir,
        snapshot_limit=args.snapshot_limit,
        bundle_limit=args.bundle_limit,
        startup_limit=args.startup_limit,
    )
    violations = check_budgets(
        args.snapshot_root,
        args.dist_dir,
        snapshot_limit=args.snapshot_limit,
        bundle_limit=args.bundle_limit,
        startup_limit=args.startup_limit,
    )
    violation_names = {violation.name for violation in violations}
    for name, actual, limit in measurements:
        status = "FAIL" if name in violation_names else "PASS"
        print(
            f"{status} {name}: {actual} bytes "
            f"(limit {limit})"
        )
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
