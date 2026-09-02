"""Stateful deterministic equipment telemetry generation."""

from datetime import datetime, timedelta
from random import Random

from portflow.domain.models import EquipmentState, TelemetryEvent

Transition = tuple[float, EquipmentState]

TRANSITIONS: dict[EquipmentState, tuple[Transition, ...]] = {
    EquipmentState.IDLE: (
        (0.80, EquipmentState.ACTIVE),
        (1.00, EquipmentState.IDLE),
    ),
    EquipmentState.ACTIVE: (
        (0.72, EquipmentState.ACTIVE),
        (0.85, EquipmentState.IDLE),
        (0.98, EquipmentState.WARNING),
        (1.00, EquipmentState.UNAVAILABLE),
    ),
    EquipmentState.WARNING: (
        (0.70, EquipmentState.ACTIVE),
        (0.85, EquipmentState.WARNING),
        (0.95, EquipmentState.UNAVAILABLE),
        (1.00, EquipmentState.MAINTENANCE),
    ),
    EquipmentState.UNAVAILABLE: (
        (0.80, EquipmentState.MAINTENANCE),
        (1.00, EquipmentState.UNAVAILABLE),
    ),
    EquipmentState.MAINTENANCE: (
        (0.90, EquipmentState.ACTIVE),
        (1.00, EquipmentState.MAINTENANCE),
    ),
}


def _next_state(current: EquipmentState, rng: Random) -> EquipmentState:
    roll = rng.random()
    for threshold, candidate in TRANSITIONS[current]:
        if roll < threshold:
            return candidate
    raise RuntimeError(f"transition table for {current.value} is incomplete")


def _measurements(state: EquipmentState, rng: Random) -> tuple[float, float]:
    if state is EquipmentState.ACTIVE:
        load = rng.uniform(45.0, 95.0)
        temperature = 35.0 + load * 0.4 + rng.uniform(-2.0, 2.0)
    elif state is EquipmentState.WARNING:
        load = rng.uniform(75.0, 100.0)
        temperature = max(65.0, 43.0 + load * 0.35 + rng.uniform(-1.0, 3.0))
    elif state is EquipmentState.IDLE:
        load = rng.uniform(0.0, 10.0)
        temperature = 28.0 + load * 0.2 + rng.uniform(-1.0, 1.0)
    else:
        load = rng.uniform(0.0, 5.0)
        temperature = rng.uniform(25.0, 35.0)
    return round(load, 2), round(temperature, 2)


def generate_telemetry(
    *,
    seed: int,
    equipment_id: str,
    terminal_id: str,
    count: int,
    start_at: datetime,
) -> list[TelemetryEvent]:
    """Generate repeatable correlated telemetry in five-minute intervals."""
    if count < 0:
        raise ValueError("count must be zero or greater")
    if start_at.tzinfo is None or start_at.utcoffset() != timedelta(0):
        raise ValueError("start_at must use UTC")

    rng = Random(seed)
    state = EquipmentState.IDLE
    events: list[TelemetryEvent] = []
    for index in range(count):
        state = _next_state(state, rng)
        load, temperature = _measurements(state, rng)
        event_timestamp = start_at + timedelta(minutes=5 * index)
        events.append(
            TelemetryEvent(
                event_id=f"evt-{seed:06d}-{index + 1:06d}",
                equipment_id=equipment_id,
                terminal_id=terminal_id,
                event_timestamp=event_timestamp,
                ingestion_timestamp=event_timestamp + timedelta(seconds=2),
                state=state,
                available=state not in {EquipmentState.UNAVAILABLE, EquipmentState.MAINTENANCE},
                load_percent=load,
                temperature_c=temperature,
            )
        )
    return events
