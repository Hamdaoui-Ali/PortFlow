from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from portflow.observability.runs import (
    STREAM_RUN_HISTORY_LIMIT,
    StreamRunHistory,
    StreamRunSummary,
    read_stream_runs,
    stream_run_history_payload,
)

FIXED_NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)

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

_MALFORMED_SCHEMA = _RUNS_SCHEMA.replace(
    "status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed'))",
    "status TEXT NOT NULL",
)


def create_state_db(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(_RUNS_SCHEMA)
    for index, row in enumerate(rows):
        values: dict[str, object] = {
            "run_id": f"run-{index:02d}",
            "topic": "portflow.telemetry",
            "bronze_dir": "data/bronze-stream",
            "batch_size": 2,
            "max_messages": 12,
            "allowed_lateness_seconds": 300,
            "poll_timeout_seconds": 1.0,
            "idle_timeout_seconds": 30.0,
            "status": "succeeded",
            "started_at": "2026-09-21T11:00:00+00:00",
            "finished_at": "2026-09-21T11:00:10+00:00",
            "consumed_count": 12,
            "bronze_row_count": 10,
            "committed_count": 5,
            "batch_count": 5,
            "duplicate_count": 1,
            "late_count": 1,
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


def create_malformed_state_db(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(_MALFORMED_SCHEMA)
    connection.execute(
        """
        INSERT INTO stream_runs(
            run_id, topic, bronze_dir, batch_size, max_messages,
            allowed_lateness_seconds, poll_timeout_seconds, idle_timeout_seconds,
            status, started_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "malformed-run",
            "portflow.telemetry",
            "data/bronze-stream",
            2,
            12,
            300,
            1.0,
            30.0,
            "corrupted",
            "2026-09-21T11:00:00+00:00",
        ),
    )
    connection.commit()
    connection.close()
    return path


def test_missing_state_is_absent_and_does_not_create_any_path(tmp_path: Path) -> None:
    state_path = tmp_path / "missing" / ".stream-state.sqlite3"

    history = read_stream_runs(state_path, now=FIXED_NOW)

    assert history.status == "absent"
    assert history.runs == ()
    assert not state_path.parent.exists()


def test_history_is_limited_and_deterministic_for_equal_start_times(tmp_path: Path) -> None:
    state_path = create_state_db(
        tmp_path / ".stream-state.sqlite3",
        [
            {
                "run_id": f"run-{index:02d}",
                "started_at": "2026-09-21T11:00:00+00:00"
                if index < 2
                else f"2026-09-21T11:{index:02d}:00+00:00",
            }
            for index in range(12)
        ],
    )

    history = read_stream_runs(state_path, now=FIXED_NOW)

    assert history.status == "ready"
    assert len(history.runs) == STREAM_RUN_HISTORY_LIMIT == 10
    ordered_keys = [(run.started_at, run.run_id) for run in history.runs]
    assert ordered_keys == sorted(ordered_keys, reverse=True)
    assert "run-00" not in {run.run_id for run in history.runs}


def test_running_run_uses_injected_now_and_keeps_missing_counters_null(tmp_path: Path) -> None:
    state_path = create_state_db(
        tmp_path / ".stream-state.sqlite3",
        [
            {
                "status": "running",
                "started_at": "2026-09-21T11:59:30+00:00",
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

    history = read_stream_runs(state_path, now=FIXED_NOW)

    run = history.runs[0]
    assert run.duration_seconds == 30.0
    assert run.finished_at is None
    assert run.consumed_messages is None
    assert run.dead_letters is None


def test_error_text_is_normalized_and_bounded(tmp_path: Path) -> None:
    state_path = create_state_db(
        tmp_path / ".stream-state.sqlite3",
        [
            {
                "status": "failed",
                "error_type": "ConsumerError",
                "error_message": "  one \n two  " + ("x " * 300),
            }
        ],
    )

    history = read_stream_runs(state_path, now=FIXED_NOW)

    error_message = history.runs[0].error_message
    assert error_message is not None
    assert error_message.startswith("one two")
    assert len(error_message) == 280
    assert "  " not in error_message


def test_invalid_row_returns_malformed_without_leaking_storage_details(tmp_path: Path) -> None:
    state_path = create_malformed_state_db(tmp_path / ".stream-state.sqlite3")

    history = read_stream_runs(state_path, now=FIXED_NOW)

    assert history.status == "malformed"
    assert history.runs == ()


def test_invalid_sqlite_file_is_unavailable_without_exposing_error(tmp_path: Path) -> None:
    state_path = tmp_path / ".stream-state.sqlite3"
    state_path.write_bytes(b"not a sqlite database")

    history = read_stream_runs(state_path, now=FIXED_NOW)

    assert history.status == "unavailable"
    assert history.runs == ()


def test_reader_preserves_state_file_bytes(tmp_path: Path) -> None:
    state_path = create_state_db(tmp_path / ".stream-state.sqlite3", [{}])
    before = state_path.read_bytes()

    read_stream_runs(state_path, now=FIXED_NOW)

    assert state_path.read_bytes() == before


def test_payload_serializes_utc_timestamps_and_nulls() -> None:
    history = StreamRunHistory(
        status="ready",
        limit=STREAM_RUN_HISTORY_LIMIT,
        runs=(
            StreamRunSummary(
                run_id="dagster-run-001",
                topic="portflow.telemetry",
                status="running",
                started_at=datetime(2026, 9, 21, 11, 59, 30, tzinfo=UTC),
                finished_at=None,
                duration_seconds=30.0,
                consumed_messages=None,
                bronze_rows=None,
                committed_batches=None,
                duplicate_messages=None,
                late_messages=None,
                dead_letters=None,
                error_type=None,
                error_message=None,
            ),
        ),
    )

    payload = stream_run_history_payload(history)

    assert payload["limit"] == 10
    run = payload["runs"][0]
    assert run["started_at"].endswith("Z")
    assert run["finished_at"] is None
