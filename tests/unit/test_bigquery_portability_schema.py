import json
from pathlib import Path

import pytest
from labs.portflow_bigquery.schema import load_schema

ROOT = Path(__file__).parents[2]
SCHEMA_PATH = ROOT / "analytics" / "portability" / "bigquery" / "schema.json"


def test_schema_declares_all_four_logical_tables() -> None:
    schema = load_schema(SCHEMA_PATH)

    assert set(schema) == {
        "telemetry_events",
        "container_movements",
        "incidents",
        "alarms",
    }
    assert {field.name for field in schema["telemetry_events"]} >= {
        "event_id",
        "terminal_id",
        "event_timestamp",
        "state",
        "available",
    }


def test_schema_loader_rejects_unknown_type(tmp_path: Path) -> None:
    invalid_schema = tmp_path / "schema.json"
    invalid_schema.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tables": {
                    "alarms": [
                        {"name": "alarm_id", "type": "BYTES", "mode": "REQUIRED"}
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid portability schema"):
        load_schema(invalid_schema)


def test_schema_loader_rejects_boolean_schema_version(tmp_path: Path) -> None:
    invalid_schema = tmp_path / "schema.json"
    invalid_schema.write_text(
        json.dumps(
            {
                "schema_version": True,
                "tables": {
                    "telemetry_events": [
                        {"name": "event_id", "type": "STRING", "mode": "REQUIRED"}
                    ],
                    "container_movements": [
                        {"name": "movement_id", "type": "STRING", "mode": "REQUIRED"}
                    ],
                    "incidents": [
                        {"name": "incident_id", "type": "STRING", "mode": "REQUIRED"}
                    ],
                    "alarms": [
                        {"name": "alarm_id", "type": "STRING", "mode": "REQUIRED"}
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid portability schema"):
        load_schema(invalid_schema)


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": 1, "tables": {}},
        {
            "schema_version": 1,
            "tables": {
                "telemetry_events": [
                    {"name": "event_id", "type": "STRING", "mode": "REQUIRED"},
                    {"name": "event_id", "type": "STRING", "mode": "REQUIRED"},
                ],
                "container_movements": [],
                "incidents": [],
                "alarms": [],
            },
        },
        {
            "schema_version": 1,
            "tables": {
                "telemetry_events": [],
                "container_movements": [],
                "incidents": [],
                "alarms": [
                    {"name": "alarm_id", "type": "STRING", "mode": "REPEATED"}
                ],
            },
        },
    ],
)
def test_schema_loader_rejects_invalid_table_or_field_contract(
    tmp_path: Path, payload: object
) -> None:
    invalid_schema = tmp_path / "schema.json"
    invalid_schema.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid portability schema"):
        load_schema(invalid_schema)


@pytest.mark.parametrize(
    "field",
    [
        {"name": "alarm_id", "type": [], "mode": "REQUIRED"},
        {"name": "alarm_id", "type": "STRING", "mode": {}},
    ],
)
def test_schema_loader_rejects_non_string_type_or_mode(tmp_path: Path, field: object) -> None:
    invalid_schema = tmp_path / "schema.json"
    invalid_schema.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tables": {
                    "telemetry_events": [
                        {"name": "event_id", "type": "STRING", "mode": "REQUIRED"}
                    ],
                    "container_movements": [
                        {"name": "movement_id", "type": "STRING", "mode": "REQUIRED"}
                    ],
                    "incidents": [
                        {"name": "incident_id", "type": "STRING", "mode": "REQUIRED"}
                    ],
                    "alarms": [field],
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid portability schema"):
        load_schema(invalid_schema)
