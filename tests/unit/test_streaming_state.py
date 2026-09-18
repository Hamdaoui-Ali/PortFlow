from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from portflow.domain.models import EquipmentState, TelemetryEvent
from portflow.streaming.codec import telemetry_payload_sha256
from portflow.streaming.state import StreamStateError, StreamStateStore


def valid_event(event_id: str = "evt-000042-000001", minute: int = 0) -> TelemetryEvent:
    timestamp = datetime(2026, 9, 2, 0, minute, tzinfo=UTC)
    return TelemetryEvent(
        event_id=event_id,
        schema_version=1,
        equipment_id="QC-001",
        terminal_id="TM-001",
        event_timestamp=timestamp,
        ingestion_timestamp=timestamp + timedelta(seconds=2),
        state=EquipmentState.ACTIVE,
        available=True,
        load_percent=50.0 + minute,
        temperature_c=55.0,
    )


def test_state_survives_reopen_and_tracks_watermark(tmp_path: Path) -> None:
    store = StreamStateStore(tmp_path / "state.sqlite3")
    event = valid_event()

    store.record_bronze(topic="portflow.telemetry", events=[event])
    store.close()

    reopened = StreamStateStore(tmp_path / "state.sqlite3")
    saved = reopened.get_event(event.event_id)

    assert saved is not None
    assert saved.outcome == "bronze"
    assert saved.payload_sha256 == telemetry_payload_sha256(event)
    assert reopened.get_watermark("portflow.telemetry") == event.ingestion_timestamp


def test_record_dead_letter_persists_reason(tmp_path: Path) -> None:
    store = StreamStateStore(tmp_path / "state.sqlite3")
    event = valid_event()

    store.record_dead_letter(
        topic="portflow.telemetry",
        event=event,
        reason_code="late_event",
    )

    saved = store.get_event(event.event_id)
    assert saved is not None
    assert saved.outcome == "dead_letter"
    assert saved.reason_code == "late_event"
    assert store.get_watermark("portflow.telemetry") is None


def test_conflicting_events_roll_back_the_entire_bronze_transaction(tmp_path: Path) -> None:
    store = StreamStateStore(tmp_path / "state.sqlite3")
    first = valid_event()
    conflict = first.model_copy(update={"load_percent": 75.0})

    with pytest.raises(StreamStateError, match="event_id"):
        store.record_bronze(topic="portflow.telemetry", events=[first, conflict])

    assert store.get_event(first.event_id) is None
    assert store.get_watermark("portflow.telemetry") is None


def test_duplicate_bronze_record_with_same_digest_is_idempotent(tmp_path: Path) -> None:
    store = StreamStateStore(tmp_path / "state.sqlite3")
    event = valid_event()

    store.record_bronze(topic="portflow.telemetry", events=[event])
    store.record_bronze(topic="portflow.telemetry", events=[event])

    assert store.get_event(event.event_id) is not None
