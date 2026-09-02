from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from portflow.domain.models import EquipmentState, TelemetryEvent


def valid_event_values() -> dict[str, object]:
    instant = datetime(2026, 9, 2, tzinfo=UTC)
    return {
        "event_id": "evt-000042-000001",
        "equipment_id": "QC-001",
        "terminal_id": "TM-001",
        "event_timestamp": instant,
        "ingestion_timestamp": instant,
        "state": EquipmentState.ACTIVE,
        "available": True,
        "load_percent": 75.0,
        "temperature_c": 60.0,
    }


def test_telemetry_applies_version_and_accepts_valid_utc_metrics() -> None:
    """Catch a contract that drops its version or rejects a valid event."""
    event = TelemetryEvent.model_validate(valid_event_values())

    assert event.schema_version == 1
    assert event.event_timestamp.tzinfo is UTC


@pytest.mark.parametrize("load_percent", [-0.1, 100.1])
def test_telemetry_rejects_load_outside_physical_range(load_percent: float) -> None:
    """Catch telemetry loads that escape the inclusive 0–100 percent range."""
    values = valid_event_values() | {"load_percent": load_percent}

    with pytest.raises(ValidationError, match="load_percent"):
        TelemetryEvent.model_validate(values)


def test_telemetry_rejects_naive_event_timestamp() -> None:
    """Catch timestamps whose timezone would make event ordering ambiguous."""
    values = valid_event_values() | {"event_timestamp": datetime(2026, 9, 2)}

    with pytest.raises(ValidationError, match="UTC"):
        TelemetryEvent.model_validate(values)


def test_unavailable_state_cannot_be_marked_available() -> None:
    """Catch contradictory state and availability values before analytics."""
    values = valid_event_values() | {
        "state": EquipmentState.UNAVAILABLE,
        "available": True,
    }

    with pytest.raises(ValidationError, match="available"):
        TelemetryEvent.model_validate(values)
