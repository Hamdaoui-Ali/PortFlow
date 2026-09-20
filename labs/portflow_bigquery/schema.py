"""Validation and loading for the committed BigQuery portability schema."""

import json
from dataclasses import dataclass
from pathlib import Path

_TABLE_NAMES = frozenset(
    {"telemetry_events", "container_movements", "incidents", "alarms"}
)
_BIGQUERY_TYPES = frozenset({"STRING", "INT64", "BOOL", "FLOAT64", "TIMESTAMP"})
_BIGQUERY_MODES = frozenset({"REQUIRED", "NULLABLE"})


@dataclass(frozen=True)
class SchemaField:
    """A scalar field accepted by the offline BigQuery portability fixture."""

    name: str
    bigquery_type: str
    mode: str


def _invalid_schema() -> ValueError:
    return ValueError("invalid portability schema")


def _read_schema_document(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise _invalid_schema() from error

def _validate_schema_document(document: object) -> dict[str, object]:
    if not isinstance(document, dict):
        raise _invalid_schema()
    schema_version = document.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != 1
    ):
        raise _invalid_schema()
    tables = document.get("tables")
    if not isinstance(tables, dict) or set(tables) != _TABLE_NAMES:
        raise _invalid_schema()
    return tables


def _parse_field(raw_field: object, seen_names: set[str]) -> SchemaField:
    if not isinstance(raw_field, dict):
        raise _invalid_schema()
    name = raw_field.get("name")
    bigquery_type = raw_field.get("type")
    mode = raw_field.get("mode")
    if (
        not isinstance(name, str)
        or not name
        or name in seen_names
        or not isinstance(bigquery_type, str)
        or not isinstance(mode, str)
        or bigquery_type not in _BIGQUERY_TYPES
        or mode not in _BIGQUERY_MODES
    ):
        raise _invalid_schema()
    seen_names.add(name)
    return SchemaField(name, bigquery_type, mode)


def _parse_fields(raw_fields: object) -> tuple[SchemaField, ...]:
    if not isinstance(raw_fields, list) or not raw_fields:
        raise _invalid_schema()
    seen_names: set[str] = set()
    return tuple(_parse_field(raw_field, seen_names) for raw_field in raw_fields)


def load_schema(path: Path) -> dict[str, tuple[SchemaField, ...]]:
    """Load the fixed four-table schema, rejecting malformed portability mappings."""
    tables = _validate_schema_document(_read_schema_document(path))

    return {
        table_name: _parse_fields(tables[table_name])
        for table_name in sorted(_TABLE_NAMES)
    }
