"""Safe paths for disposable PF-107 artifacts."""

import stat
from pathlib import Path, PurePosixPath, PureWindowsPath

DEFAULT_ARTIFACT_ROOT = Path(".databricks") / "pf107"
_REPARSE_POINT_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class ArtifactPathError(ValueError):
    """Raised when a PF-107 artifact path is unsafe or escapes its root."""


def _absolute_without_resolving(path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else Path.cwd() / path


def _path_components(path: Path) -> tuple[Path, ...]:
    absolute = _absolute_without_resolving(path)
    current = Path(absolute.anchor)
    components: list[Path] = []
    for part in absolute.parts:
        if part == absolute.anchor:
            continue
        current /= part
        components.append(current)
    return tuple(components)


def _is_reparse_point(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise ArtifactPathError("artifact path cannot be inspected") from error

    if stat.S_ISLNK(metadata.st_mode):
        return True

    is_junction = getattr(path, "is_junction", None)
    try:
        if callable(is_junction) and is_junction():
            return True
    except OSError as error:
        raise ArtifactPathError("artifact path cannot be inspected") from error

    attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(attributes & _REPARSE_POINT_ATTRIBUTE)


def _reject_reparse_components(path: Path, message: str) -> None:
    for component in _path_components(path):
        if _is_reparse_point(component):
            raise ArtifactPathError(message)


def _validate_relative_path(relative_path: str) -> None:
    """Reject syntax that could escape the root on either host OS."""
    if not isinstance(relative_path, str):
        raise ArtifactPathError("artifact path must remain below artifact root")

    windows = PureWindowsPath(relative_path)
    posix = PurePosixPath(relative_path)
    raw_parts = relative_path.replace("\\", "/").split("/")
    if (
        not relative_path
        or relative_path == "."
        or windows.drive
        or windows.root
        or posix.is_absolute()
        or any(part in {".", ".."} for part in raw_parts)
        or "\\" in relative_path
        or ":" in relative_path
    ):
        raise ArtifactPathError("artifact path must remain below artifact root")


def resolve_artifact_root(
    candidate: Path | None = None,
    *,
    repository_root: Path | None = None,
) -> Path:
    """Resolve a PF-107 root while rejecting reparse points and escapes."""
    base = _absolute_without_resolving(repository_root or Path.cwd())
    artifact_candidate = base / DEFAULT_ARTIFACT_ROOT
    _reject_reparse_components(
        artifact_candidate,
        "artifact root must not contain symbolic links or reparse points",
    )
    artifact_root = artifact_candidate.resolve()

    if candidate is None:
        return artifact_root

    requested_candidate = _absolute_without_resolving(candidate)
    _reject_reparse_components(
        requested_candidate,
        "artifact root must not contain symbolic links or reparse points",
    )
    requested = requested_candidate.resolve()
    try:
        requested.relative_to(artifact_root)
    except ValueError as error:
        raise ArtifactPathError("artifact root must remain below .databricks/pf107") from error
    return requested


def resolve_artifact_path(root: Path, relative_path: str) -> Path:
    """Resolve a relative artifact name after checking every existing component."""
    _validate_relative_path(relative_path)
    root_candidate = _absolute_without_resolving(root)
    _reject_reparse_components(
        root_candidate,
        "artifact path must not contain symbolic links or reparse points",
    )
    candidate_path = root_candidate / relative_path
    _reject_reparse_components(
        candidate_path,
        "artifact path must not contain symbolic links or reparse points",
    )

    resolved_root = root_candidate.resolve()
    candidate = candidate_path.resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as error:
        raise ArtifactPathError("artifact path must remain below artifact root") from error
    return candidate
