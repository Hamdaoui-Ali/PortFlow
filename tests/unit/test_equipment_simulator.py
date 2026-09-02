from datetime import UTC, datetime, timedelta

from portflow.domain.models import EquipmentState
from portflow.simulator.equipment import generate_telemetry

START = datetime(2026, 9, 2, tzinfo=UTC)


def generator_arguments() -> dict[str, object]:
    return {
        "seed": 42,
        "equipment_id": "QC-001",
        "terminal_id": "TM-001",
        "count": 40,
        "start_at": START,
    }


def test_same_seed_produces_identical_events_and_unique_ids() -> None:
    """Catch nondeterminism or identifier collisions in repeatable fixtures."""
    first = generate_telemetry(**generator_arguments())
    second = generate_telemetry(**generator_arguments())

    assert first == second
    assert len(first) == 40
    assert len({event.event_id for event in first}) == 40
    assert first[0].event_id == "evt-000042-000001"


def test_events_advance_in_five_minute_utc_intervals() -> None:
    """Catch unordered or timezone-ambiguous simulator output."""
    events = generate_telemetry(**generator_arguments())

    assert [event.event_timestamp for event in events] == [
        START + timedelta(minutes=5 * index) for index in range(40)
    ]
    assert all(event.event_timestamp.utcoffset() == timedelta(0) for event in events)


def test_state_controls_availability_and_measurement_ranges() -> None:
    """Catch independent random values that contradict equipment state."""
    events = generate_telemetry(**generator_arguments())

    assert any(event.state is EquipmentState.UNAVAILABLE for event in events)
    for event in events:
        if event.state in {EquipmentState.UNAVAILABLE, EquipmentState.MAINTENANCE}:
            assert event.available is False
            assert event.load_percent <= 5.0
        if event.state is EquipmentState.WARNING:
            assert event.available is True
            assert event.temperature_c >= 65.0
