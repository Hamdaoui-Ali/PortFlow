"""Read-only Prometheus metrics derived from the PF-103 run state."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

StreamRunStatus = Literal["running", "succeeded", "failed"]

_STATUSES: tuple[StreamRunStatus, ...] = ("running", "succeeded", "failed")
_COUNTER_COLUMNS = {
    "consumed_count": "consumed_messages_total",
    "bronze_row_count": "bronze_rows_total",
    "committed_count": "committed_batches_total",
    "duplicate_count": "duplicate_messages_total",
    "late_count": "late_messages_total",
    "dead_letter_count": "dead_letters_total",
}


@dataclass(frozen=True, slots=True)
class StreamMetricsSnapshot:
    """One scrape-time view of the local stream run table."""

    state_store_available: bool
    collection_success: bool
    runs_count: dict[StreamRunStatus, int]
    last_run_status: StreamRunStatus | None
    last_run_started_at: datetime | None
    last_run_finished_at: datetime | None
    last_run_duration_seconds: float
    consumed_messages_total: int
    bronze_rows_total: int
    committed_batches_total: int
    duplicate_messages_total: int
    late_messages_total: int
    dead_letters_total: int


def collect_stream_metrics(
    state_path: Path,
    *,
    now: datetime,
) -> StreamMetricsSnapshot:
    """Read stream run metadata without creating or mutating the state file."""
    connection: sqlite3.Connection | None = None
    try:
        now_utc = _as_utc(now)
        connection = sqlite3.connect(
            f"{state_path.resolve().as_uri()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                run_id,
                status,
                started_at,
                finished_at,
                consumed_count,
                bronze_row_count,
                committed_count,
                duplicate_count,
                late_count,
                dead_letter_count
            FROM stream_runs
            ORDER BY started_at DESC, run_id DESC
            """
        ).fetchall()
        return _build_snapshot(rows, now=now_utc)
    except (FileNotFoundError, OSError, sqlite3.Error, TypeError, ValueError):
        return _empty_snapshot()
    finally:
        if connection is not None:
            connection.close()


def render_prometheus(snapshot: StreamMetricsSnapshot) -> str:
    """Render a snapshot using Prometheus text exposition format."""
    lines: list[str] = []
    _append_metric(
        lines,
        "portflow_stream_state_store_available",
        "State store read availability.",
        _bool_value(snapshot.state_store_available),
    )
    _append_metric(
        lines,
        "portflow_stream_metrics_collection_success",
        "Most recent metrics collection success.",
        _bool_value(snapshot.collection_success),
    )
    _append_metric(
        lines,
        "portflow_stream_runs_count",
        "Stored stream runs by lifecycle status.",
        None,
    )
    for status in _STATUSES:
        lines.append(
            f'portflow_stream_runs_count{{status="{status}"}} '
            f"{snapshot.runs_count[status]}"
        )

    _append_metric(lines, "portflow_stream_last_run_status", "Latest stream run status.", None)
    for status in _STATUSES:
        value = int(snapshot.last_run_status == status)
        lines.append(f'portflow_stream_last_run_status{{status="{status}"}} {value}')

    _append_metric(
        lines,
        "portflow_stream_last_run_started_at_seconds",
        "UTC start time of the latest stream run.",
        _timestamp_value(snapshot.last_run_started_at),
    )
    _append_metric(
        lines,
        "portflow_stream_last_run_finished_at_seconds",
        "UTC finish time of the latest stream run.",
        _timestamp_value(snapshot.last_run_finished_at),
    )
    _append_metric(
        lines,
        "portflow_stream_last_run_duration_seconds",
        "Duration of the latest stream run in seconds.",
        snapshot.last_run_duration_seconds,
    )

    aggregate_metrics = (
        ("consumed_messages_total", snapshot.consumed_messages_total, "Consumed stream messages."),
        ("bronze_rows_total", snapshot.bronze_rows_total, "Bronze rows reported by stream runs."),
        (
            "committed_batches_total",
            snapshot.committed_batches_total,
            "Committed batches reported by stream runs.",
        ),
        (
            "duplicate_messages_total",
            snapshot.duplicate_messages_total,
            "Duplicate messages reported by stream runs.",
        ),
        (
            "late_messages_total",
            snapshot.late_messages_total,
            "Late messages reported by stream runs.",
        ),
        (
            "dead_letters_total",
            snapshot.dead_letters_total,
            "Dead letters reported by stream runs.",
        ),
    )
    for suffix, value, help_text in aggregate_metrics:
        _append_metric(lines, f"portflow_stream_{suffix}", help_text, value)

    return "\n".join(lines) + "\n"


def _build_snapshot(rows: list[sqlite3.Row], *, now: datetime) -> StreamMetricsSnapshot:
    counts = {status: 0 for status in _STATUSES}
    totals = {name: 0 for name in _COUNTER_COLUMNS.values()}
    latest: tuple[str, StreamRunStatus, datetime, datetime | None] | None = None

    for row in rows:
        raw_status = cast(str, row["status"])
        if raw_status not in _STATUSES:
            raise ValueError(f"invalid stream run status: {raw_status}")
        status = raw_status
        started_at = _parse_timestamp(cast(str, row["started_at"]))
        raw_finished_at = cast(str | None, row["finished_at"])
        finished_at = None if raw_finished_at is None else _parse_timestamp(raw_finished_at)
        counts[status] += 1

        for column, suffix in _COUNTER_COLUMNS.items():
            value = row[column]
            if value is not None:
                totals[suffix] += int(value)

        run_id = cast(str, row["run_id"])
        if latest is None or (started_at, run_id) > (latest[2], latest[0]):
            latest = (run_id, status, started_at, finished_at)

    if latest is None:
        return StreamMetricsSnapshot(
            state_store_available=True,
            collection_success=True,
            runs_count=counts,
            last_run_status=None,
            last_run_started_at=None,
            last_run_finished_at=None,
            last_run_duration_seconds=0.0,
            consumed_messages_total=totals["consumed_messages_total"],
            bronze_rows_total=totals["bronze_rows_total"],
            committed_batches_total=totals["committed_batches_total"],
            duplicate_messages_total=totals["duplicate_messages_total"],
            late_messages_total=totals["late_messages_total"],
            dead_letters_total=totals["dead_letters_total"],
        )

    _, latest_status, latest_started_at, latest_finished_at = latest
    end_time = latest_finished_at or now
    duration = max(0.0, (end_time - latest_started_at).total_seconds())
    return StreamMetricsSnapshot(
        state_store_available=True,
        collection_success=True,
        runs_count=counts,
        last_run_status=latest_status,
        last_run_started_at=latest_started_at,
        last_run_finished_at=latest_finished_at,
        last_run_duration_seconds=duration,
        consumed_messages_total=totals["consumed_messages_total"],
        bronze_rows_total=totals["bronze_rows_total"],
        committed_batches_total=totals["committed_batches_total"],
        duplicate_messages_total=totals["duplicate_messages_total"],
        late_messages_total=totals["late_messages_total"],
        dead_letters_total=totals["dead_letters_total"],
    )


def _empty_snapshot() -> StreamMetricsSnapshot:
    return StreamMetricsSnapshot(
        state_store_available=False,
        collection_success=False,
        runs_count={status: 0 for status in _STATUSES},
        last_run_status=None,
        last_run_started_at=None,
        last_run_finished_at=None,
        last_run_duration_seconds=0.0,
        consumed_messages_total=0,
        bronze_rows_total=0,
        committed_batches_total=0,
        duplicate_messages_total=0,
        late_messages_total=0,
        dead_letters_total=0,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _parse_timestamp(value: str) -> datetime:
    return _as_utc(datetime.fromisoformat(value))


def _bool_value(value: bool) -> int:
    return int(value)


def _timestamp_value(value: datetime | None) -> float:
    return 0.0 if value is None else value.timestamp()


def _append_metric(
    lines: list[str],
    name: str,
    help_text: str,
    value: int | float | None,
) -> None:
    lines.append(f"# HELP {name} {help_text}")
    lines.append(f"# TYPE {name} gauge")
    if value is not None:
        lines.append(f"{name} {value}")
