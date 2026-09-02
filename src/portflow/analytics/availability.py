"""Equipment-availability KPI calculation."""

from collections.abc import Sequence
from dataclasses import dataclass

from portflow.domain.models import TelemetryEvent


@dataclass(frozen=True, slots=True)
class AvailabilityKpi:
    """Available intervals divided by scheduled telemetry intervals."""

    available_intervals: int
    scheduled_intervals: int
    value: float | None


def calculate_availability(events: Sequence[TelemetryEvent]) -> AvailabilityKpi:
    """Calculate availability without inventing a zero for an empty period."""
    scheduled = len(events)
    available = sum(event.available for event in events)
    value = available / scheduled if scheduled else None
    return AvailabilityKpi(
        available_intervals=available,
        scheduled_intervals=scheduled,
        value=value,
    )
