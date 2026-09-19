from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from portflow.domain.models import EquipmentState, TelemetryEvent
from portflow.streaming.codec import telemetry_payload_sha256
from portflow.streaming.consumer import ConsumeReport
from portflow.streaming.state import StreamRunInputs, StreamStateError, StreamStateStore


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


def test_stream_run_persists_inputs_and_running_status(tmp_path: Path) -> None:
    inputs = stream_run_inputs(tmp_path)
    store = StreamStateStore(tmp_path / "state.sqlite3")
    store.start_run(run_id="dagster-run-1", inputs=inputs)
    store.close()

    reopened = StreamStateStore(tmp_path / "state.sqlite3")
    run = reopened.get_run("dagster-run-1")

    assert run is not None
    assert run.status == "running"
    assert run.topic == inputs.topic
    assert run.bronze_dir == inputs.bronze_dir
    assert run.started_at.tzinfo == UTC
    assert run.finished_at is None
    assert run.error_type is None


def stream_run_inputs(tmp_path: Path) -> StreamRunInputs:
    return StreamRunInputs(
        topic="portflow.telemetry",
        bronze_dir=tmp_path / "bronze",
        batch_size=2,
        max_messages=12,
        allowed_lateness_seconds=300,
        poll_timeout_seconds=1.0,
        idle_timeout_seconds=30.0,
    )


def test_stream_run_success_persists_report_and_finished_at(tmp_path: Path) -> None:
    store = StreamStateStore(tmp_path / "state.sqlite3")
    store.start_run(run_id="dagster-success-1", inputs=stream_run_inputs(tmp_path))
    report = ConsumeReport(
        consumed_count=12,
        bronze_row_count=10,
        committed_count=3,
        batch_count=3,
        duplicate_count=1,
        late_count=1,
        dead_letter_count=2,
    )
    finished_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

    store.record_run_success(
        run_id="dagster-success-1",
        report=report,
        finished_at=finished_at,
    )

    run = store.get_run("dagster-success-1")
    assert run is not None
    assert run.status == "succeeded"
    assert run.finished_at == finished_at
    assert run.consumed_count == report.consumed_count
    assert run.bronze_row_count == report.bronze_row_count
    assert run.committed_count == report.committed_count
    assert run.batch_count == report.batch_count
    assert run.duplicate_count == report.duplicate_count
    assert run.late_count == report.late_count
    assert run.dead_letter_count == report.dead_letter_count
    assert run.error_type is None
    assert run.error_message is None


def test_stream_run_failure_persists_error_and_finished_at(tmp_path: Path) -> None:
    store = StreamStateStore(tmp_path / "state.sqlite3")
    store.start_run(run_id="dagster-failure-1", inputs=stream_run_inputs(tmp_path))
    finished_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

    store.record_run_failure(
        run_id="dagster-failure-1",
        error_type="ValueError",
        error_message="bad config",
        finished_at=finished_at,
    )

    run = store.get_run("dagster-failure-1")
    assert run is not None
    assert run.status == "failed"
    assert run.finished_at == finished_at
    assert run.error_type == "ValueError"
    assert run.error_message == "bad config"
    assert run.consumed_count is None


def test_stream_run_rejects_duplicate_start_and_terminal_transitions(tmp_path: Path) -> None:
    store = StreamStateStore(tmp_path / "state.sqlite3")
    inputs = stream_run_inputs(tmp_path)
    store.start_run(run_id="dagster-transition-1", inputs=inputs)
    finished_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

    with pytest.raises(StreamStateError, match="already exists"):
        store.start_run(run_id="dagster-transition-1", inputs=inputs)

    store.record_run_success(
        run_id="dagster-transition-1",
        report=ConsumeReport(1, 1, 1, 1),
        finished_at=finished_at,
    )

    with pytest.raises(StreamStateError, match="terminal"):
        store.record_run_failure(
            run_id="dagster-transition-1",
            error_type="RuntimeError",
            error_message="too late",
            finished_at=finished_at,
        )

    with pytest.raises(StreamStateError, match="not found"):
        store.record_run_success(
            run_id="missing-run",
            report=ConsumeReport(1, 1, 1, 1),
            finished_at=finished_at,
        )
