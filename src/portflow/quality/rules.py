"""Reason-coded validation rules for Bronze source rows."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal, cast

from portflow.ingestion.postgres_to_bronze import TABLE_SPECS

VALID_REASON_CODES = (
    "SCHEMA_INVALID",
    "RANGE_INVALID",
    "REFERENCE_INVALID",
    "TEMPORAL_INVALID",
    "DUPLICATE_KEY",
)

ReasonCode = Literal[
    "SCHEMA_INVALID",
    "RANGE_INVALID",
    "REFERENCE_INVALID",
    "TEMPORAL_INVALID",
    "DUPLICATE_KEY",
]


@dataclass(frozen=True, slots=True)
class ReferenceSet:
    """Reference identifiers available to validate foreign-key fields."""

    terminal_ids: frozenset[str]
    equipment_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One stable reason code and human-readable detail."""

    code: ReasonCode
    detail: str


_ID_PATTERNS = {
    "terminal_id": re.compile(r"^TM-\d{3}$"),
    "equipment_id": re.compile(r"^[A-Z]{2,4}-\d{3}$"),
    "event_id": re.compile(r"^evt-\d{6}-\d{6}$"),
    "alarm_id": re.compile(r"^alm-\d{6}$"),
    "incident_id": re.compile(r"^inc-\d{6}$"),
    "maintenance_order_id": re.compile(r"^mnt-\d{6}$"),
    "movement_id": re.compile(r"^mov-\d{6}$"),
}
_ENUM_VALUES = {
    "equipment_type": {"QUAY_CRANE", "RTG", "REACH_STACKER"},
    "state": {"IDLE", "ACTIVE", "WARNING", "UNAVAILABLE", "MAINTENANCE"},
    "severity": {"INFO", "WARNING", "CRITICAL", "MINOR", "MAJOR"},
    "status": {"OPEN", "RESOLVED", "PLANNED", "IN_PROGRESS", "COMPLETED"},
    "movement_type": {"GATE_IN", "GATE_OUT", "LOAD", "DISCHARGE"},
}
_TABLE_ENUM_COLUMNS = {
    "equipment": {"equipment_type"},
    "telemetry_events": {"state"},
    "alarms": {"severity"},
    "incidents": {"severity", "status"},
    "maintenance_orders": {"status"},
    "container_movements": {"movement_type"},
}
_DATETIME_COLUMNS = {
    "created_at",
    "updated_at",
    "event_timestamp",
    "ingestion_timestamp",
    "opened_at",
    "cleared_at",
    "resolved_at",
    "started_at",
    "completed_at",
    "source_updated_at",
    "extracted_at",
}


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _is_utc_datetime(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() == timedelta(0)
    )


def _add_issue(issues: dict[ReasonCode, str], code: ReasonCode, detail: str) -> None:
    issues.setdefault(code, detail)


def _required_schema_issues(table_name: str, row: Mapping[str, object]) -> dict[ReasonCode, str]:
    issues: dict[ReasonCode, str] = {}
    spec = TABLE_SPECS.get(table_name)
    if spec is None:
        _add_issue(issues, "SCHEMA_INVALID", f"unsupported table {table_name!r}")
        return issues

    missing = [column for column in spec.columns if column not in row]
    if missing:
        _add_issue(issues, "SCHEMA_INVALID", f"missing columns: {', '.join(missing)}")
        return issues

    for column in spec.columns:
        value = row[column]
        if (
            (column.endswith("_id") or column in {"name", "timezone_name", "code", "root_cause"})
            and (not isinstance(value, str) or not value.strip())
        ):
            _add_issue(issues, "SCHEMA_INVALID", f"{column} must be a non-empty string")
        if column in _DATETIME_COLUMNS:
            nullable = column in {"cleared_at", "resolved_at", "completed_at"}
            if (value is None and not nullable) or (
                value is not None and not _is_utc_datetime(value)
            ):
                _add_issue(issues, "SCHEMA_INVALID", f"{column} must be a UTC datetime")
        if (
            column in _ID_PATTERNS
            and isinstance(value, str)
            and not _ID_PATTERNS[column].match(value)
        ):
            _add_issue(issues, "SCHEMA_INVALID", f"{column} has an invalid identifier")
        if (
            column in _TABLE_ENUM_COLUMNS.get(table_name, set())
            and value not in _ENUM_VALUES[column]
        ):
            _add_issue(issues, "SCHEMA_INVALID", f"{column} has an invalid value")

    if "schema_version" in row:
        if not isinstance(row["schema_version"], int) or isinstance(row["schema_version"], bool):
            _add_issue(issues, "SCHEMA_INVALID", "schema_version must be an integer")
        elif row["schema_version"] != 1:
            _add_issue(issues, "SCHEMA_INVALID", "schema_version must be 1")
    if "commissioning_date" in row and not isinstance(row["commissioning_date"], date):
        _add_issue(issues, "SCHEMA_INVALID", "commissioning_date must be a date")
    if "available" in row and not isinstance(row["available"], bool):
        _add_issue(issues, "SCHEMA_INVALID", "available must be boolean")
    for column in ("load_percent", "temperature_c"):
        if column in row and not _is_number(row[column]):
            _add_issue(issues, "SCHEMA_INVALID", f"{column} must be numeric")
    return issues


def _range_issues(table_name: str, row: Mapping[str, object]) -> dict[ReasonCode, str]:
    issues: dict[ReasonCode, str] = {}
    if table_name == "telemetry_events":
        load = row.get("load_percent")
        temperature = row.get("temperature_c")
        if _is_number(load) and not 0 <= float(cast(int | float | Decimal, load)) <= 100:
            _add_issue(issues, "RANGE_INVALID", "load_percent must be between 0 and 100")
        if _is_number(temperature) and not -20 <= float(
            cast(int | float | Decimal, temperature)
        ) <= 150:
            _add_issue(issues, "RANGE_INVALID", "temperature_c must be between -20 and 150")
    return issues


def _reference_issues(
    table_name: str,
    row: Mapping[str, object],
    reference_set: ReferenceSet,
) -> dict[ReasonCode, str]:
    issues: dict[ReasonCode, str] = {}
    checks: list[tuple[str, frozenset[str]]] = []
    if table_name in {"equipment", "container_movements"}:
        checks.append(("terminal_id", reference_set.terminal_ids))
    if table_name in {
        "telemetry_events",
        "alarms",
        "incidents",
        "maintenance_orders",
        "container_movements",
    }:
        checks.append(("equipment_id", reference_set.equipment_ids))
    if table_name == "telemetry_events":
        checks.append(("terminal_id", reference_set.terminal_ids))
    for column, identifiers in checks:
        value = row.get(column)
        if isinstance(value, str) and value not in identifiers:
            _add_issue(issues, "REFERENCE_INVALID", f"{column} {value!r} is not referenced")
    return issues


def _temporal_issues(table_name: str, row: Mapping[str, object]) -> dict[ReasonCode, str]:
    issues: dict[ReasonCode, str] = {}

    def check_order(left_name: str, right_name: str) -> None:
        left = row.get(left_name)
        right = row.get(right_name)
        if (
            _is_utc_datetime(left)
            and _is_utc_datetime(right)
            and cast(datetime, right) < cast(datetime, left)
        ):
            _add_issue(issues, "TEMPORAL_INVALID", f"{right_name} must not precede {left_name}")

    check_order("created_at", "updated_at")
    if table_name == "telemetry_events":
        check_order("event_timestamp", "ingestion_timestamp")
        state = row.get("state")
        available = row.get("available")
        if (
            isinstance(state, str)
            and state in {"UNAVAILABLE", "MAINTENANCE"}
            and available is True
        ):
            _add_issue(issues, "TEMPORAL_INVALID", "unavailable states must not be available")
        if (
            isinstance(state, str)
            and state in {"IDLE", "ACTIVE", "WARNING"}
            and available is False
        ):
            _add_issue(issues, "TEMPORAL_INVALID", "available states must be available")
    elif table_name == "alarms":
        if row.get("cleared_at") is not None:
            check_order("opened_at", "cleared_at")
    elif table_name == "incidents":
        if row.get("resolved_at") is not None:
            check_order("opened_at", "resolved_at")
        if row.get("status") == "RESOLVED" and row.get("resolved_at") is None:
            _add_issue(issues, "TEMPORAL_INVALID", "resolved incidents require resolved_at")
        if row.get("status") == "OPEN" and row.get("resolved_at") is not None:
            _add_issue(issues, "TEMPORAL_INVALID", "open incidents cannot have resolved_at")
    elif table_name == "maintenance_orders":
        if row.get("completed_at") is not None:
            check_order("started_at", "completed_at")
        if row.get("status") == "COMPLETED" and row.get("completed_at") is None:
            _add_issue(issues, "TEMPORAL_INVALID", "completed orders require completed_at")
        if row.get("status") != "COMPLETED" and row.get("completed_at") is not None:
            _add_issue(issues, "TEMPORAL_INVALID", "unfinished orders cannot have completed_at")
    return issues


def validate_row(
    table_name: str,
    row: Mapping[str, object],
    reference_set: ReferenceSet,
    *,
    seen_keys: set[str] | None = None,
) -> list[ValidationIssue]:
    """Validate one source row and return stable, ordered reason codes."""
    issues = _required_schema_issues(table_name, row)
    issues.update(_range_issues(table_name, row))
    issues.update(_reference_issues(table_name, row, reference_set))
    issues.update(_temporal_issues(table_name, row))
    spec = TABLE_SPECS.get(table_name)
    if seen_keys is not None and spec is not None:
        key = row.get(spec.primary_key)
        if isinstance(key, str) and key in seen_keys:
            _add_issue(issues, "DUPLICATE_KEY", f"duplicate {spec.primary_key} {key!r}")
    return [ValidationIssue(code, issues[code]) for code in VALID_REASON_CODES if code in issues]
