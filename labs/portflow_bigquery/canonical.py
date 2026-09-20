"""Canonicalize offline BigQuery portability results for stable comparison."""

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import cast

RESULT_FIELDS: tuple[str, ...] = (
    "terminal_id",
    "source_period_start",
    "source_period_end",
    "available_intervals",
    "scheduled_intervals",
    "active_intervals",
    "available_time_minutes",
    "resolved_incident_count",
    "repair_minutes",
    "qualifying_failure_count",
    "operating_hours",
    "throughput",
    "average_dwell_minutes",
    "availability",
    "utilization",
    "mttr_minutes",
    "mtbf_hours",
    "active_incidents",
    "critical_alarms",
)

INTEGER_FIELDS = {
    "available_intervals",
    "scheduled_intervals",
    "active_intervals",
    "available_time_minutes",
    "resolved_incident_count",
    "qualifying_failure_count",
    "throughput",
    "active_incidents",
    "critical_alarms",
}
NULLABLE_FIELDS = {
    "average_dwell_minutes",
    "availability",
    "utilization",
    "mttr_minutes",
    "mtbf_hours",
}
_TIMESTAMP_FIELDS = {"source_period_start", "source_period_end"}


def canonicalize_rows(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Normalize result rows into the strict, deterministic comparison shape."""
    canonical = [_canonicalize_row(row) for row in rows]
    seen_terminal_ids: set[str] = set()
    for row in canonical:
        terminal_id = cast(str, row["terminal_id"])
        if terminal_id in seen_terminal_ids:
            raise ValueError("duplicate terminal_id")
        seen_terminal_ids.add(terminal_id)
    canonical.sort(key=lambda row: cast(str, row["terminal_id"]))
    return canonical


def result_sha256(rows: Iterable[Mapping[str, object]]) -> str:
    """Return the SHA-256 digest of newline-terminated canonical JSON."""
    payload = json.dumps(
        canonicalize_rows(rows),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonicalize_row(row: Mapping[str, object]) -> dict[str, object]:
    missing = [field for field in RESULT_FIELDS if field not in row]
    if missing:
        raise ValueError(f"missing result fields: {', '.join(missing)}")

    unexpected = [field for field in row if field not in RESULT_FIELDS]
    if unexpected:
        raise ValueError(f"unexpected result fields: {', '.join(sorted(unexpected))}")

    normalized: dict[str, object] = {}
    for field in RESULT_FIELDS:
        value = row[field]
        if field == "terminal_id":
            normalized[field] = _normalize_terminal_id(value)
        elif field in _TIMESTAMP_FIELDS:
            normalized[field] = _normalize_timestamp(field, value)
        elif field in INTEGER_FIELDS:
            normalized[field] = _normalize_integer(field, value)
        else:
            normalized[field] = _normalize_metric(field, value)
    return normalized


def _normalize_terminal_id(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("terminal_id must be a non-empty string")
    return value


def _normalize_timestamp(field: str, value: object) -> str:
    if not isinstance(value, datetime):
        raise ValueError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _normalize_integer(field: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _normalize_metric(field: str, value: object) -> float | None:
    if value is None:
        if field in NULLABLE_FIELDS:
            return None
        raise ValueError(f"{field} must not be null")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field} must be finite")
    return round(numeric, 6)
