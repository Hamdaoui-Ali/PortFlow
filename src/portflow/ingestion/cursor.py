"""Durable composite cursors for incremental source extraction."""

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True, order=True, slots=True)
class SourceCursor:
    """A deterministic `(updated_at, primary_key)` source position."""

    updated_at: datetime
    primary_key: str

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() != timedelta(0):
            raise ValueError("cursor timestamp must use UTC")
        if not self.primary_key:
            raise ValueError("cursor primary_key must not be empty")


def _timestamp_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("cursor updated_at must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("cursor updated_at is not valid ISO-8601") from error
    return parsed


class CursorStore:
    """Read and atomically replace a JSON mapping of source cursors."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, SourceCursor]:
        """Load all saved cursors, returning an empty mapping when absent."""
        if not self.path.exists():
            return {}
        try:
            raw: object = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid cursor state at {self.path}") from error
        if not isinstance(raw, dict):
            raise ValueError(f"cursor state at {self.path} must be a JSON object")

        cursors: dict[str, SourceCursor] = {}
        for table_name, raw_cursor in raw.items():
            if not isinstance(table_name, str) or not isinstance(raw_cursor, dict):
                raise ValueError(f"invalid cursor entry for {table_name!r}")
            if set(raw_cursor) != {"primary_key", "updated_at"}:
                raise ValueError(f"invalid cursor fields for {table_name!r}")
            primary_key = raw_cursor.get("primary_key")
            if not isinstance(primary_key, str):
                raise ValueError(f"cursor primary_key for {table_name!r} must be a string")
            cursors[table_name] = SourceCursor(
                _parse_timestamp(raw_cursor.get("updated_at")),
                primary_key,
            )
        return cursors

    def save(
        self,
        cursors: Mapping[str, SourceCursor | None],
        replace: Callable[..., None] = os.replace,
    ) -> None:
        """Atomically save cursors without damaging a previous valid state."""
        serializable: dict[str, dict[str, str]] = {}
        for table_name, cursor in cursors.items():
            if not table_name:
                raise ValueError("cursor table names must not be empty")
            if cursor is not None:
                serializable[table_name] = {
                    "primary_key": cursor.primary_key,
                    "updated_at": _timestamp_text(cursor.updated_at),
                }

        payload = (
            json.dumps(serializable, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_name(f"{self.path.name}.tmp")
        try:
            with temporary_path.open("wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            replace(temporary_path, self.path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise


def read_cursor(path: Path, table_name: str) -> SourceCursor | None:
    """Read one table cursor from a state file."""
    return CursorStore(path).load().get(table_name)


def write_cursor(path: Path, table_name: str, cursor: SourceCursor) -> None:
    """Merge one table cursor into an existing state file."""
    store = CursorStore(path)
    cursors = store.load()
    cursors[table_name] = cursor
    store.save(cursors)
