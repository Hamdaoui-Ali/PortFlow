"""Small, independently testable implementations of the Gold KPI formulas."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from statistics import mean


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("fixture timestamps must be ISO-8601 strings")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(None):
        raise ValueError("fixture timestamps must use UTC")
    return parsed.astimezone(UTC)


def _rows(case: Mapping[str, object], key: str) -> Sequence[Mapping[str, object]]:
    value = case.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"fixture {key!r} must be a list")
    return [row for row in value if isinstance(row, Mapping)]


def _movement_metrics(movements: Sequence[Mapping[str, object]]) -> dict[str, float | int | None]:
    by_container: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in movements:
        container_ref = row.get("container_ref")
        if isinstance(container_ref, str):
            by_container[container_ref].append(row)

    dwell_minutes: list[float] = []
    completed_pairs = 0
    for rows in by_container.values():
        ordered = sorted(
            rows,
            key=lambda row: _timestamp(row["event_timestamp"]),
        )
        entry: datetime | None = None
        for row in ordered:
            movement_type = row.get("movement_type")
            if movement_type in {"GATE_IN", "LOAD"}:
                entry = _timestamp(row["event_timestamp"])
            elif movement_type in {"GATE_OUT", "DISCHARGE"} and entry is not None:
                exit_at = _timestamp(row["event_timestamp"])
                if exit_at >= entry:
                    completed_pairs += 1
                    dwell_minutes.append((exit_at - entry).total_seconds() / 60.0)
                    entry = None
    return {
        "throughput": completed_pairs,
        "average_dwell_minutes": mean(dwell_minutes) if dwell_minutes else None,
    }


def calculate_fixture_case(case: Mapping[str, object]) -> dict[str, float | int | None]:
    """Calculate documented KPIs from a compact, JSON-friendly fixture case."""
    telemetry = _rows(case, "telemetry")
    scheduled_intervals = len(telemetry)
    available_intervals = sum(row.get("available") is True for row in telemetry)
    active_intervals = sum(row.get("state") == "ACTIVE" for row in telemetry)
    availability = (
        available_intervals / scheduled_intervals if scheduled_intervals else None
    )
    utilization = active_intervals / available_intervals if available_intervals else None

    resolved_durations: list[float] = []
    for incident in _rows(case, "incidents"):
        opened_at = incident.get("opened_at")
        resolved_at = incident.get("resolved_at")
        if (
            incident.get("status") == "RESOLVED"
            and opened_at is not None
            and resolved_at is not None
        ):
            duration = _timestamp(resolved_at) - _timestamp(opened_at)
            if duration.total_seconds() >= 0:
                resolved_durations.append(duration.total_seconds() / 60.0)
    mttr_minutes = mean(resolved_durations) if resolved_durations else None

    operating_hours = case.get("operating_hours", 0)
    failures = case.get("qualifying_failure_count", 0)
    if not isinstance(operating_hours, (int, float)) or isinstance(operating_hours, bool):
        raise ValueError("operating_hours must be numeric")
    if not isinstance(failures, int) or isinstance(failures, bool) or failures < 0:
        raise ValueError("qualifying_failure_count must be a non-negative integer")
    mtbf_hours = operating_hours / failures if failures else None
    interval_minutes = case.get("interval_minutes", 5)
    if not isinstance(interval_minutes, int) or isinstance(interval_minutes, bool):
        raise ValueError("interval_minutes must be an integer")
    movement_metrics = _movement_metrics(_rows(case, "movements"))

    metrics: dict[str, float | int | None] = {
        "throughput": movement_metrics["throughput"],
        "average_dwell_minutes": movement_metrics["average_dwell_minutes"],
        "available_intervals": available_intervals,
        "scheduled_intervals": scheduled_intervals,
        "active_intervals": active_intervals,
        "available_time_minutes": available_intervals
        * interval_minutes,
        "resolved_incident_count": len(resolved_durations),
        "repair_minutes": sum(resolved_durations),
        "qualifying_failure_count": failures,
        "operating_hours": float(operating_hours),
        "availability": availability,
        "utilization": utilization,
        "mttr_minutes": mttr_minutes,
        "mtbf_hours": mtbf_hours,
    }

    include = case.get("include")
    if isinstance(include, list):
        return {key: metrics[key] for key in include if isinstance(key, str) and key in metrics}
    return metrics
