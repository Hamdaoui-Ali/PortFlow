"""Canonical first-slice JSON snapshot writer."""

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from portflow.analytics.availability import calculate_availability
from portflow.domain.models import TelemetryEvent

SNAPSHOT_ID = "demo-v1"


def _utc_text(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical_json(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_first_snapshot(output_dir: Path, events: Sequence[TelemetryEvent]) -> Path:
    """Write one immutable overview dataset and its validating manifest."""
    if not events:
        raise ValueError("at least one telemetry event is required for snapshot metadata")

    terminal_ids = {event.terminal_id for event in events}
    if len(terminal_ids) != 1:
        raise ValueError("the first snapshot must contain exactly one terminal")

    availability = calculate_availability(events)
    overview = {
        "availability": {
            "available_intervals": availability.available_intervals,
            "scheduled_intervals": availability.scheduled_intervals,
            "value": availability.value,
        },
        "schema_version": 1,
        "terminal_id": next(iter(terminal_ids)),
    }
    overview_bytes = _canonical_json(overview)
    overview_relative_path = Path("snapshots") / SNAPSHOT_ID / "overview.json"
    overview_path = output_dir / overview_relative_path
    overview_path.parent.mkdir(parents=True, exist_ok=True)
    overview_path.write_bytes(overview_bytes)

    event_times = [event.event_timestamp for event in events]
    generated_at = max(event.ingestion_timestamp for event in events)
    manifest = {
        "datasets": {
            "overview": {
                "path": overview_relative_path.as_posix(),
                "sha256": hashlib.sha256(overview_bytes).hexdigest(),
            }
        },
        "generated_at": _utc_text(generated_at),
        "quality_status": "PASS",
        "record_counts": {"telemetry": len(events)},
        "schema_version": 1,
        "snapshot_id": SNAPSHOT_ID,
        "source_period_end": _utc_text(max(event_times)),
        "source_period_start": _utc_text(min(event_times)),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_bytes(_canonical_json(manifest))
    return manifest_path
