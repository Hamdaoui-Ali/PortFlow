from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from portflow.observability.metrics import (
    StreamMetricsSnapshot,
    collect_stream_metrics,
    render_prometheus,
)

_RUNS_SCHEMA = """
CREATE TABLE stream_runs (
    run_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    bronze_dir TEXT NOT NULL,
    batch_size INTEGER NOT NULL,
    max_messages INTEGER NOT NULL,
    allowed_lateness_seconds INTEGER NOT NULL,
    poll_timeout_seconds REAL NOT NULL,
    idle_timeout_seconds REAL NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    consumed_count INTEGER,
    bronze_row_count INTEGER,
    committed_count INTEGER,
    batch_count INTEGER,
    duplicate_count INTEGER,
    late_count INTEGER,
    dead_letter_count INTEGER,
    error_type TEXT,
    error_message TEXT
)
"""

_MALFORMED_RUNS_SCHEMA = _RUNS_SCHEMA.replace(
    "status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed'))",
    "status TEXT NOT NULL",
)


def create_state_db(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(_RUNS_SCHEMA)
    for row in rows:
        values = {
            "run_id": "dagster-fixture",
            "topic": "portflow.telemetry",
            "bronze_dir": "data/bronze-stream",
            "batch_size": 2,
            "max_messages": 12,
            "allowed_lateness_seconds": 300,
            "poll_timeout_seconds": 1.0,
            "idle_timeout_seconds": 30.0,
            "status": "succeeded",
            "started_at": "2026-09-19T11:00:00+00:00",
            "finished_at": "2026-09-19T11:00:10+00:00",
            "consumed_count": 0,
            "bronze_row_count": 0,
            "committed_count": 0,
            "batch_count": 0,
            "duplicate_count": 0,
            "late_count": 0,
            "dead_letter_count": 0,
            "error_type": None,
            "error_message": None,
        }
        values.update(row)
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        connection.execute(
            f"INSERT INTO stream_runs ({columns}) VALUES ({placeholders})",
            tuple(values.values()),
        )
    connection.commit()
    connection.close()
    return path


def create_malformed_state_db(path: Path, *, status: str, started_at: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(_MALFORMED_RUNS_SCHEMA)
    connection.execute(
        """
        INSERT INTO stream_runs(
            run_id, topic, bronze_dir, batch_size, max_messages,
            allowed_lateness_seconds, poll_timeout_seconds, idle_timeout_seconds,
            status, started_at, finished_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "malformed-fixture",
            "portflow.telemetry",
            "data/bronze-stream",
            2,
            12,
            300,
            1.0,
            30.0,
            status,
            started_at,
            None,
        ),
    )
    connection.commit()
    connection.close()
    return path


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_collect_missing_state_is_empty_and_does_not_create_file(tmp_path: Path) -> None:
    state_path = tmp_path / "missing" / ".stream-state.sqlite3"

    snapshot = collect_stream_metrics(
        state_path,
        now=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
    )

    assert snapshot.state_store_available is False
    assert snapshot.collection_success is False
    assert snapshot.runs_count == {"running": 0, "succeeded": 0, "failed": 0}
    assert snapshot.last_run_status is None
    assert not state_path.exists()
    assert not state_path.parent.exists()


def test_collect_sums_successful_counters_and_selects_latest_run(tmp_path: Path) -> None:
    state_path = create_state_db(
        tmp_path / ".stream-state.sqlite3",
        rows=[
            {
                "run_id": "dagster-old",
                "status": "succeeded",
                "started_at": "2026-09-19T11:00:00+00:00",
                "finished_at": "2026-09-19T11:00:10+00:00",
                "consumed_count": 4,
                "bronze_row_count": 3,
                "committed_count": 2,
                "duplicate_count": 1,
                "late_count": 0,
                "dead_letter_count": 0,
            },
            {
                "run_id": "dagster-new",
                "status": "failed",
                "started_at": "2026-09-19T11:30:00+00:00",
                "finished_at": "2026-09-19T11:30:05+00:00",
                "consumed_count": None,
                "bronze_row_count": None,
                "committed_count": None,
                "duplicate_count": None,
                "late_count": None,
                "dead_letter_count": None,
            },
        ],
    )

    snapshot = collect_stream_metrics(
        state_path,
        now=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
    )

    assert snapshot.collection_success is True
    assert snapshot.runs_count == {"running": 0, "succeeded": 1, "failed": 1}
    assert snapshot.last_run_status == "failed"
    assert snapshot.last_run_duration_seconds == 5.0
    assert snapshot.consumed_messages_total == 4
    assert snapshot.bronze_rows_total == 3
    assert snapshot.committed_batches_total == 2
    assert snapshot.duplicate_messages_total == 1
    assert snapshot.late_messages_total == 0
    assert snapshot.dead_letters_total == 0


def test_running_latest_run_uses_injected_now_and_zero_finished_timestamp(
    tmp_path: Path,
) -> None:
    state_path = create_state_db(
        tmp_path / ".stream-state.sqlite3",
        rows=[
            {
                "run_id": "dagster-running",
                "status": "running",
                "started_at": "2026-09-19T11:59:30+00:00",
                "finished_at": None,
                "consumed_count": None,
                "bronze_row_count": None,
                "committed_count": None,
                "duplicate_count": None,
                "late_count": None,
                "dead_letter_count": None,
            }
        ],
    )

    snapshot = collect_stream_metrics(
        state_path,
        now=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
    )

    assert snapshot.last_run_duration_seconds == 30.0
    assert snapshot.last_run_finished_at is None


@pytest.mark.parametrize(
    ("status", "started_at"),
    [
        ("corrupted", "2026-09-19T11:00:00+00:00"),
        ("succeeded", "not-a-timestamp"),
    ],
)
def test_invalid_timestamp_or_status_marks_collection_unsuccessful(
    tmp_path: Path,
    status: str,
    started_at: str,
) -> None:
    state_path = create_malformed_state_db(
        tmp_path / ".stream-state.sqlite3",
        status=status,
        started_at=started_at,
    )

    snapshot = collect_stream_metrics(
        state_path,
        now=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
    )

    assert snapshot.state_store_available is False
    assert snapshot.collection_success is False


def test_collection_does_not_modify_read_only_state_file(tmp_path: Path) -> None:
    state_path = create_state_db(
        tmp_path / ".stream-state.sqlite3",
        rows=[{"run_id": "unchanged-fixture"}],
    )
    before = file_digest(state_path)

    collect_stream_metrics(
        state_path,
        now=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
    )

    assert file_digest(state_path) == before


def test_rendered_metrics_have_only_bounded_status_labels() -> None:
    text = render_prometheus(
        StreamMetricsSnapshot(
            state_store_available=True,
            collection_success=True,
            runs_count={"running": 0, "succeeded": 1, "failed": 0},
            last_run_status="succeeded",
            last_run_started_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
            last_run_finished_at=datetime(2026, 9, 19, 12, 0, 10, tzinfo=UTC),
            last_run_duration_seconds=10.0,
            consumed_messages_total=1,
            bronze_rows_total=1,
            committed_batches_total=1,
            duplicate_messages_total=0,
            late_messages_total=0,
            dead_letters_total=0,
        )
    )

    assert 'portflow_stream_runs_count{status="succeeded"} 1' in text
    assert "portflow_stream_state_store_available 1" in text
    assert "run_id" not in text
    assert "error_message" not in text
    assert "dagster" not in text
