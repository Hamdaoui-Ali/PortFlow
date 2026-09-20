"""Path-boundary helpers for benchmark artifacts."""

import stat
from pathlib import Path

_REPARSE_POINT_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _path_components(path: Path) -> tuple[Path, ...]:
    absolute = path if path.is_absolute() else Path.cwd() / path
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
        raise ValueError("benchmark path cannot be inspected") from error
    if stat.S_ISLNK(metadata.st_mode):
        return True
    is_junction = getattr(path, "is_junction", None)
    try:
        if callable(is_junction) and is_junction():
            return True
    except OSError as error:
        raise ValueError("benchmark path cannot be inspected") from error
    attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(attributes & _REPARSE_POINT_ATTRIBUTE)


def reject_reparse_components(path: Path, *, message: str) -> None:
    """Reject symlink or junction components before resolving a path."""
    if any(_is_reparse_point(component) for component in _path_components(path)):
        raise ValueError(message)
