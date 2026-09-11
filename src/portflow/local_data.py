"""Typed local import contract and safe PostgreSQL writes."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from portflow.ingestion.postgres_to_bronze import TABLE_SPECS
from portflow.quality.rules import ReferenceSet, ValidationIssue, validate_row

ColumnKind = Literal["string", "integer", "number", "boolean", "date", "datetime"]


@dataclass(frozen=True, slots=True)
class ColumnSchema:
    """Metadata used by the local JSON editor and normalizer."""

    name: str
    kind: ColumnKind
    required: bool
    nullable: bool
    description: str


@dataclass(frozen=True, slots=True)
class TableSchema:
    """Metadata for one allow-listed operational source table."""

    table_name: str
    primary_key: str
    columns: tuple[ColumnSchema, ...]


@dataclass(frozen=True, slots=True)
class ImportIssue:
    """One row-level problem suitable for an API response."""

    row_index: int
    field: str | None
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class ImportReport:
    """Counts returned after one transactional table import."""

    table_name: str
    received_count: int
    inserted_count: int
    updated_count: int


class UnsupportedTableError(ValueError):
    """Raised when a local import names a table outside TABLE_SPECS."""


class ImportValidationError(ValueError):
    """Raised when one or more imported records fail normalization or validation."""

    def __init__(self, issues: Sequence[ImportIssue]) -> None:
        self.issues = tuple(issues)
        summary = "; ".join(
            f"row {issue.row_index}: {issue.detail}" for issue in self.issues
        )
        super().__init__(summary or "import validation failed")


_SCHEMA_COLUMNS: dict[str, tuple[ColumnSchema, ...]] = {
    "terminals": (
        ColumnSchema("terminal_id", "string", True, False, "Stable terminal identifier."),
        ColumnSchema("name", "string", True, False, "Human-readable terminal name."),
        ColumnSchema("timezone_name", "string", True, False, "IANA timezone name."),
        ColumnSchema("created_at", "datetime", True, False, "UTC creation timestamp."),
        ColumnSchema("updated_at", "datetime", True, False, "UTC update timestamp."),
    ),
    "equipment": (
        ColumnSchema("equipment_id", "string", True, False, "Stable equipment identifier."),
        ColumnSchema("terminal_id", "string", True, False, "Referenced terminal identifier."),
        ColumnSchema("equipment_type", "string", True, False, "Operational equipment type."),
        ColumnSchema("commissioning_date", "date", True, False, "Equipment commissioning date."),
        ColumnSchema("created_at", "datetime", True, False, "UTC creation timestamp."),
        ColumnSchema("updated_at", "datetime", True, False, "UTC update timestamp."),
    ),
    "telemetry_events": (
        ColumnSchema("event_id", "string", True, False, "Stable telemetry event identifier."),
        ColumnSchema("schema_version", "integer", True, False, "Telemetry schema version; use 1."),
        ColumnSchema("equipment_id", "string", True, False, "Referenced equipment identifier."),
        ColumnSchema("terminal_id", "string", True, False, "Referenced terminal identifier."),
        ColumnSchema("event_timestamp", "datetime", True, False, "UTC event timestamp."),
        ColumnSchema("ingestion_timestamp", "datetime", True, False, "UTC ingestion timestamp."),
        ColumnSchema("state", "string", True, False, "Equipment state."),
        ColumnSchema("available", "boolean", True, False, "Whether the equipment is available."),
        ColumnSchema("load_percent", "number", True, False, "Load percentage from 0 to 100."),
        ColumnSchema("temperature_c", "number", True, False, "Temperature in Celsius."),
        ColumnSchema("created_at", "datetime", True, False, "UTC creation timestamp."),
        ColumnSchema("updated_at", "datetime", True, False, "UTC update timestamp."),
    ),
    "alarms": (
        ColumnSchema("alarm_id", "string", True, False, "Stable alarm identifier."),
        ColumnSchema("equipment_id", "string", True, False, "Referenced equipment identifier."),
        ColumnSchema("severity", "string", True, False, "Alarm severity."),
        ColumnSchema("code", "string", True, False, "Alarm code."),
        ColumnSchema("opened_at", "datetime", True, False, "UTC alarm opening timestamp."),
        ColumnSchema("cleared_at", "datetime", False, True, "UTC clearing timestamp, if cleared."),
        ColumnSchema("created_at", "datetime", True, False, "UTC creation timestamp."),
        ColumnSchema("updated_at", "datetime", True, False, "UTC update timestamp."),
    ),
    "incidents": (
        ColumnSchema("incident_id", "string", True, False, "Stable incident identifier."),
        ColumnSchema("equipment_id", "string", True, False, "Referenced equipment identifier."),
        ColumnSchema("severity", "string", True, False, "Incident severity."),
        ColumnSchema("status", "string", True, False, "Incident lifecycle status."),
        ColumnSchema("opened_at", "datetime", True, False, "UTC incident opening timestamp."),
        ColumnSchema(
            "resolved_at", "datetime", False, True, "UTC resolution timestamp, if resolved."
        ),
        ColumnSchema("root_cause", "string", True, False, "Concise root-cause description."),
        ColumnSchema("created_at", "datetime", True, False, "UTC creation timestamp."),
        ColumnSchema("updated_at", "datetime", True, False, "UTC update timestamp."),
    ),
    "maintenance_orders": (
        ColumnSchema(
            "maintenance_order_id", "string", True, False, "Stable maintenance order identifier."
        ),
        ColumnSchema("equipment_id", "string", True, False, "Referenced equipment identifier."),
        ColumnSchema("status", "string", True, False, "Maintenance lifecycle status."),
        ColumnSchema("started_at", "datetime", True, False, "UTC maintenance start timestamp."),
        ColumnSchema(
            "completed_at", "datetime", False, True, "UTC completion timestamp, if complete."
        ),
        ColumnSchema("created_at", "datetime", True, False, "UTC creation timestamp."),
        ColumnSchema("updated_at", "datetime", True, False, "UTC update timestamp."),
    ),
    "container_movements": (
        ColumnSchema("movement_id", "string", True, False, "Stable movement identifier."),
        ColumnSchema("terminal_id", "string", True, False, "Referenced terminal identifier."),
        ColumnSchema("equipment_id", "string", True, False, "Referenced equipment identifier."),
        ColumnSchema("movement_type", "string", True, False, "Container movement type."),
        ColumnSchema("container_ref", "string", True, False, "Container reference."),
        ColumnSchema("event_timestamp", "datetime", True, False, "UTC movement timestamp."),
        ColumnSchema("created_at", "datetime", True, False, "UTC creation timestamp."),
        ColumnSchema("updated_at", "datetime", True, False, "UTC update timestamp."),
    ),
}


def _validate_schema_registry() -> None:
    for table_name, table_spec in TABLE_SPECS.items():
        columns = _SCHEMA_COLUMNS.get(table_name)
        if columns is None or tuple(column.name for column in columns) != table_spec.columns:
            raise RuntimeError(f"local schema does not match TABLE_SPECS for {table_name}")


_validate_schema_registry()


def get_local_schema() -> tuple[TableSchema, ...]:
    """Return the seven supported table schemas in ingestion order."""
    return tuple(
        TableSchema(
            table_name=table_name,
            primary_key=table_spec.primary_key,
            columns=_SCHEMA_COLUMNS[table_name],
        )
        for table_name, table_spec in TABLE_SPECS.items()
    )


def _table_schema(table_name: str) -> TableSchema:
    table_spec = TABLE_SPECS.get(table_name)
    if table_spec is None:
        raise UnsupportedTableError(f"unsupported source table: {table_name}")
    return TableSchema(
        table_name=table_name,
        primary_key=table_spec.primary_key,
        columns=_SCHEMA_COLUMNS[table_name],
    )


def _normalize_value(column: ColumnSchema, value: object) -> object:
    if value is None:
        if column.nullable:
            return None
        raise ValueError(f"{column.name} is required")

    if column.kind == "string":
        if not isinstance(value, str):
            raise ValueError(f"{column.name} must be a string")
        return value

    if column.kind == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{column.name} must be an integer")
        return value

    if column.kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError(f"{column.name} must be numeric")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{column.name} must be finite")
        return value

    if column.kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{column.name} must be boolean")
        return value

    if column.kind == "date":
        if isinstance(value, datetime):
            raise ValueError(f"{column.name} must be a date")
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError as error:
                raise ValueError(f"{column.name} must be an ISO date") from error
        raise ValueError(f"{column.name} must be an ISO date")

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as error:
            raise ValueError(f"{column.name} must be an ISO datetime") from error
    else:
        raise ValueError(f"{column.name} must be an ISO datetime")

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{column.name} must include a timezone")
    return parsed.astimezone(UTC)


def normalize_records(
    table_name: str,
    records: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Normalize JSON records into the typed values used by PostgreSQL."""
    schema = _table_schema(table_name)
    expected_names = {column.name for column in schema.columns}
    normalized_records: list[dict[str, object]] = []
    issues: list[ImportIssue] = []

    for row_index, record in enumerate(records):
        record_issues: list[ImportIssue] = []
        extra_names = sorted(set(record) - expected_names)
        record_issues.extend(
            ImportIssue(row_index, name, "SCHEMA_INVALID", f"unknown field {name!r}")
            for name in extra_names
        )
        normalized: dict[str, object] = {}
        for column in schema.columns:
            if column.name not in record:
                if column.nullable:
                    normalized[column.name] = None
                else:
                    record_issues.append(
                        ImportIssue(
                            row_index,
                            column.name,
                            "SCHEMA_INVALID",
                            f"missing required field {column.name}",
                        )
                    )
                continue
            try:
                normalized[column.name] = _normalize_value(column, record[column.name])
            except ValueError as error:
                record_issues.append(
                    ImportIssue(row_index, column.name, "SCHEMA_INVALID", str(error))
                )
        if record_issues:
            issues.extend(record_issues)
        else:
            normalized_records.append(normalized)

    if issues:
        raise ImportValidationError(issues)
    return normalized_records


def _field_for_validation_issue(
    issue: ValidationIssue,
    *,
    table_name: str,
) -> str | None:
    if issue.code == "DUPLICATE_KEY":
        return TABLE_SPECS[table_name].primary_key
    for column in TABLE_SPECS[table_name].columns:
        if issue.detail.startswith(f"{column} "):
            return column
    return None


def _validate_normalized_records(
    table_name: str,
    records: Sequence[Mapping[str, object]],
    reference_set: ReferenceSet,
) -> list[ImportIssue]:
    issues: list[ImportIssue] = []
    seen_keys: set[str] = set()
    primary_key = TABLE_SPECS[table_name].primary_key
    for row_index, record in enumerate(records):
        key = record.get(primary_key)
        row_issues = validate_row(
            table_name,
            record,
            reference_set,
            seen_keys=seen_keys,
        )
        if isinstance(key, str):
            seen_keys.add(key)
        issues.extend(
            ImportIssue(
                row_index=row_index,
                field=_field_for_validation_issue(validation_issue, table_name=table_name),
                code=validation_issue.code,
                detail=validation_issue.detail,
            )
            for validation_issue in row_issues
        )
    return issues


def validate_records(
    table_name: str,
    records: Sequence[Mapping[str, object]],
    reference_set: ReferenceSet,
) -> list[ImportIssue]:
    """Return quality-rule issues after JSON normalization."""
    normalized = normalize_records(table_name, records)
    return _validate_normalized_records(table_name, normalized, reference_set)
