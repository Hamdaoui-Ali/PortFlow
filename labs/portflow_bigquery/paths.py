from pathlib import Path

DEFAULT_ARTIFACT_ROOT = Path(".portability") / "bigquery"


class ArtifactPathError(ValueError):
    """Raised when a portability artifact path escapes the allowed root."""


def resolve_artifact_root(
    candidate: Path | None = None,
    *,
    repository_root: Path | None = None,
) -> Path:
    base = (repository_root or Path.cwd()).resolve()
    if candidate is None:
        requested = (base / DEFAULT_ARTIFACT_ROOT).resolve()
    else:
        requested = candidate.resolve()
        if requested.name != "bigquery" or requested.parent.name != ".portability":
            raise ArtifactPathError("artifact root must remain below .portability/bigquery")
    return requested


def resolve_artifact_path(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ArtifactPathError("artifact path must remain below artifact root") from error
    return candidate
