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


def load_schema(path: Path) -> dict[str, tuple[SchemaField, ...]]:
    """Load the fixed four-table schema, rejecting malformed portability mappings."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise _invalid_schema() from error

    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise _invalid_schema()
    tables = document.get("tables")
    if not isinstance(tables, dict) or set(tables) != _TABLE_NAMES:
        raise _invalid_schema()

    schema: dict[str, tuple[SchemaField, ...]] = {}
    for table_name in sorted(_TABLE_NAMES):
        raw_fields = tables[table_name]
        if not isinstance(raw_fields, list) or not raw_fields:
            raise _invalid_schema()
        fields: list[SchemaField] = []
        seen_names: set[str] = set()
        for raw_field in raw_fields:
            if not isinstance(raw_field, dict):
                raise _invalid_schema()
            name = raw_field.get("name")
            bigquery_type = raw_field.get("type")
            mode = raw_field.get("mode")
            if (
                not isinstance(name, str)
                or not name
                or name in seen_names
                or bigquery_type not in _BIGQUERY_TYPES
                or mode not in _BIGQUERY_MODES
            ):
                raise _invalid_schema()
            seen_names.add(name)
            fields.append(SchemaField(name, bigquery_type, mode))
        schema[table_name] = tuple(fields)
    return schema
