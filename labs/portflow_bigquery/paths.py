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
    artifact_root = (base / DEFAULT_ARTIFACT_ROOT).resolve()
    if candidate is None:
        return artifact_root
    requested = candidate.resolve()
    try:
        requested.relative_to(artifact_root)
    except ValueError as error:
        raise ArtifactPathError(
            "artifact root must remain below .portability/bigquery"
        ) from error
    return requested


def resolve_artifact_path(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ArtifactPathError("artifact path must remain below artifact root") from error
    return candidate
