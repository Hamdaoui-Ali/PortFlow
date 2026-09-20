"""Stable result normalization and hashing."""

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from typing import cast

RESULT_FIELDS = (
    "terminal_id",
    "state",
    "event_count",
    "available_event_count",
    "average_load_percent",
    "average_temperature_c",
)
_INTEGER_FIELDS = {"event_count", "available_event_count"}
_FLOAT_FIELDS = {"average_load_percent", "average_temperature_c"}


def _normalize_integer(field: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _normalize_float(field: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field} must be finite")
    return round(numeric, 6)


def _normalize_string(field: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _normalize_field(field: str, value: object) -> object:
    if field in _INTEGER_FIELDS:
        return _normalize_integer(field, value)
    if field in _FLOAT_FIELDS:
        return _normalize_float(field, value)
    return _normalize_string(field, value)


def _canonicalize_row(row: Mapping[str, object]) -> dict[str, object]:
    missing = [field for field in RESULT_FIELDS if field not in row]
    if missing:
        raise ValueError(f"missing result fields: {', '.join(missing)}")
    return {field: _normalize_field(field, row[field]) for field in RESULT_FIELDS}


def canonicalize_rows(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Return sorted result rows with stable types and six-decimal averages."""
    canonical = [_canonicalize_row(row) for row in rows]
    canonical.sort(key=lambda row: (cast(str, row["terminal_id"]), cast(str, row["state"])))
    return canonical


def result_sha256(rows: Iterable[Mapping[str, object]]) -> str:
    """Hash canonical rows as stable JSON with a terminating newline."""
    payload = json.dumps(
        canonicalize_rows(rows),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
