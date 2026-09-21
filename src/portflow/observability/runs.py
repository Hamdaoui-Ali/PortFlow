"""Read-only stream-run history derived from the PF-103 state store."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from portflow.observability.metrics import StreamRunStatus

RunHistoryStatus = Literal["ready", "absent", "malformed", "unavailable"]
STREAM_RUN_HISTORY_LIMIT = 10
_STREAM_RUN_STATUSES: frozenset[str] = frozenset({"running", "succeeded", "failed"})


@dataclass(frozen=True, slots=True)
class StreamRunSummary:
    """Safe, bounded fields for one stream-run history row."""

    run_id: str
    topic: str
    status: StreamRunStatus
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float
    consumed_messages: int | None
    bronze_rows: int | None
    committed_batches: int | None
    duplicate_messages: int | None
    late_messages: int | None
    dead_letters: int | None
    error_type: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class StreamRunHistory:
    """One bounded view of the local stream-run state."""

    status: RunHistoryStatus
    limit: int
    runs: tuple[StreamRunSummary, ...]


def read_stream_runs(state_path: Path, *, now: datetime) -> StreamRunHistory:
    """Read the latest stream runs without creating or mutating state."""
    try:
        if not state_path.is_file():
            return _history("absent")
        resolved_path = state_path.resolve()
    except OSError:
        return _history("unavailable")

    connection: sqlite3.Connection | None = None
    try:
        now_utc = _as_utc(now)
        connection = sqlite3.connect(
            f"{resolved_path.as_uri()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                run_id,
                topic,
                status,
                started_at,
                finished_at,
                consumed_count,
                bronze_row_count,
                committed_count,
                duplicate_count,
                late_count,
                dead_letter_count,
                error_type,
                error_message
            FROM stream_runs
            ORDER BY started_at DESC, run_id DESC
            LIMIT ?
            """,
            (STREAM_RUN_HISTORY_LIMIT,),
        ).fetchall()
        runs = tuple(_row_to_summary(row, now=now_utc) for row in rows)
        return StreamRunHistory(
            status="ready",
            limit=STREAM_RUN_HISTORY_LIMIT,
            runs=runs,
        )
    except (OSError, sqlite3.Error):
        return _history("unavailable")
    except (TypeError, ValueError):
        return _history("malformed")
    finally:
        if connection is not None:
            connection.close()


def stream_run_history_payload(history: StreamRunHistory) -> dict[str, object]:
    """Serialize history without exposing storage paths or raw exceptions."""
    return {
        "status": history.status,
        "limit": history.limit,
        "runs": [_summary_payload(run) for run in history.runs],
    }


def _row_to_summary(row: sqlite3.Row, *, now: datetime) -> StreamRunSummary:
    raw_status = _required_text(row["status"], "status")
    if raw_status not in _STREAM_RUN_STATUSES:
        raise ValueError(f"invalid stream run status: {raw_status}")

    started_at = _parse_timestamp(_required_text(row["started_at"], "started_at"))
    finished_at = _optional_timestamp(row["finished_at"])
    end_time = finished_at or now
    duration_seconds = max(0.0, (end_time - started_at).total_seconds())
    return StreamRunSummary(
        run_id=_required_text(row["run_id"], "run_id"),
        topic=_required_text(row["topic"], "topic"),
        status=cast(StreamRunStatus, raw_status),
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration_seconds,
        consumed_messages=_optional_integer(row["consumed_count"], "consumed_count"),
        bronze_rows=_optional_integer(row["bronze_row_count"], "bronze_row_count"),
        committed_batches=_optional_integer(row["committed_count"], "committed_count"),
        duplicate_messages=_optional_integer(row["duplicate_count"], "duplicate_count"),
        late_messages=_optional_integer(row["late_count"], "late_count"),
        dead_letters=_optional_integer(row["dead_letter_count"], "dead_letter_count"),
        error_type=_optional_text(row["error_type"], "error_type"),
        error_message=_bounded_error_message(row["error_message"]),
    )


def _summary_payload(run: StreamRunSummary) -> dict[str, object]:
    return {
        "run_id": run.run_id,
        "topic": run.topic,
        "status": run.status,
        "started_at": _timestamp_text(run.started_at),
        "finished_at": None if run.finished_at is None else _timestamp_text(run.finished_at),
        "duration_seconds": run.duration_seconds,
        "consumed_messages": run.consumed_messages,
        "bronze_rows": run.bronze_rows,
        "committed_batches": run.committed_batches,
        "duplicate_messages": run.duplicate_messages,
        "late_messages": run.late_messages,
        "dead_letters": run.dead_letters,
        "error_type": run.error_type,
        "error_message": run.error_message,
    }


def _history(status: RunHistoryStatus) -> StreamRunHistory:
    return StreamRunHistory(status=status, limit=STREAM_RUN_HISTORY_LIMIT, runs=())


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _parse_timestamp(value: str) -> datetime:
    return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _timestamp_text(value: datetime) -> str:
    return _as_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"stored {field} must be non-empty text")
    return value


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"stored {field} must be text or null")
    return value


def _optional_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    return _parse_timestamp(_required_text(value, "finished_at"))


def _optional_integer(value: object, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"stored {field} must be an integer or null")
    return value


def _bounded_error_message(value: object) -> str | None:
    text = _optional_text(value, "error_message")
    if text is None:
        return None
    normalized = " ".join(text.split())
    return normalized[:280] or None
