from datetime import UTC, datetime, timedelta

from portflow.analytics.availability import calculate_availability
from portflow.domain.models import EquipmentState, TelemetryEvent


def build_events(available: list[bool]) -> list[TelemetryEvent]:
    start = datetime(2026, 9, 2, tzinfo=UTC)
    return [
        TelemetryEvent(
            event_id=f"evt-000042-{index + 1:06d}",
            equipment_id="QC-001",
            terminal_id="TM-001",
            event_timestamp=start + timedelta(minutes=5 * index),
            ingestion_timestamp=start + timedelta(minutes=5 * index, seconds=2),
            state=EquipmentState.ACTIVE if value else EquipmentState.UNAVAILABLE,
            available=value,
            load_percent=75.0 if value else 0.0,
            temperature_c=60.0 if value else 30.0,
        )
        for index, value in enumerate(available)
    ]


def test_availability_uses_available_over_scheduled_intervals() -> None:
    """Catch a wrong numerator, denominator, or percentage scale."""
    result = calculate_availability(build_events([True, True, False, True]))

    assert result.available_intervals == 3
    assert result.scheduled_intervals == 4
    assert result.value == 0.75


def test_availability_is_unavailable_without_scheduled_intervals() -> None:
    """Catch a fabricated zero when no denominator exists."""
    result = calculate_availability([])

    assert result.available_intervals == 0
    assert result.scheduled_intervals == 0
    assert result.value is None
