"""Durable local state for restart-safe telemetry stream decisions."""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from portflow.domain.models import TelemetryEvent
from portflow.streaming.codec import telemetry_payload_sha256

if TYPE_CHECKING:
    from portflow.streaming.consumer import ConsumeReport

EventOutcome = Literal["bronze", "dead_letter"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_events (
    event_id TEXT PRIMARY KEY,
    payload_sha256 TEXT NOT NULL,
    ingestion_timestamp TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('bronze', 'dead_letter')),
    reason_code TEXT
);

CREATE TABLE IF NOT EXISTS watermarks (
    topic TEXT PRIMARY KEY,
    max_ingestion_timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stream_runs (
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
);
"""


@dataclass(frozen=True, slots=True)
class ProcessedEventState:
    """Persisted outcome for one validated telemetry event."""

    event_id: str
    payload_sha256: str
    ingestion_timestamp: datetime
    outcome: EventOutcome
    reason_code: str | None


StreamRunStatus = Literal["running", "succeeded", "failed"]


@dataclass(frozen=True, slots=True)
class StreamRunInputs:
    """Normalized non-secret inputs for one Dagster-managed stream run."""

    topic: str
    bronze_dir: Path
    batch_size: int
    max_messages: int
    allowed_lateness_seconds: int
    poll_timeout_seconds: float
    idle_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class StreamRun:
    """Persisted lifecycle and outcome metadata for one stream run."""

    run_id: str
    topic: str
    bronze_dir: Path
    batch_size: int
    max_messages: int
    allowed_lateness_seconds: int
    poll_timeout_seconds: float
    idle_timeout_seconds: float
    status: StreamRunStatus
    started_at: datetime
    finished_at: datetime | None
    consumed_count: int | None
    bronze_row_count: int | None
    committed_count: int | None
    batch_count: int | None
    duplicate_count: int | None
    late_count: int | None
    dead_letter_count: int | None
    error_type: str | None
    error_message: str | None


class StreamStateError(RuntimeError):
    """Raised when durable stream state cannot be read or updated safely."""


class StreamStateStore:
    """Store event outcomes and topic watermarks in one local SQLite file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._closed = False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self.path)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.executescript(_SCHEMA)
            self._connection.commit()
        except (OSError, sqlite3.Error) as exc:
            connection = getattr(self, "_connection", None)
            if connection is not None:
                connection.close()
            raise StreamStateError(f"could not initialize stream state at {path}") from exc

    def get_event(self, event_id: str) -> ProcessedEventState | None:
        """Return the stored decision for an event ID, if present."""
        if not event_id:
            raise ValueError("event_id must not be empty")
        try:
            row = self._connection.execute(
                """
                SELECT event_id, payload_sha256, ingestion_timestamp, outcome, reason_code
                FROM processed_events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise StreamStateError(f"could not read event state for {event_id}") from exc
        return None if row is None else _row_to_event_state(row)

    def get_watermark(self, topic: str) -> datetime | None:
        """Return the greatest accepted ingestion timestamp for a topic."""
        _require_text(topic, "topic")
        try:
            row = self._connection.execute(
                "SELECT max_ingestion_timestamp FROM watermarks WHERE topic = ?",
                (topic,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise StreamStateError(f"could not read watermark for {topic}") from exc
        if row is None:
            return None
        return _parse_timestamp(cast(str, row["max_ingestion_timestamp"]))

    def start_run(self, *, run_id: str, inputs: StreamRunInputs) -> None:
        """Persist a new Dagster-managed run in the running state."""
        _require_text(run_id, "run_id")
        _validate_stream_run_inputs(inputs)
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO stream_runs(
                        run_id,
                        topic,
                        bronze_dir,
                        batch_size,
                        max_messages,
                        allowed_lateness_seconds,
                        poll_timeout_seconds,
                        idle_timeout_seconds,
                        status,
                        started_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)
                    """,
                    (
                        run_id,
                        inputs.topic,
                        str(inputs.bronze_dir),
                        inputs.batch_size,
                        inputs.max_messages,
                        inputs.allowed_lateness_seconds,
                        inputs.poll_timeout_seconds,
                        inputs.idle_timeout_seconds,
                        _timestamp_text(datetime.now(UTC)),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise StreamStateError(f"stream run already exists: {run_id}") from exc
        except sqlite3.Error as exc:
            raise StreamStateError(f"could not start stream run {run_id}") from exc

    def get_run(self, run_id: str) -> StreamRun | None:
        """Return run metadata by Dagster run ID, if present."""
        _require_text(run_id, "run_id")
        try:
            row = self._connection.execute(
                """
                SELECT
                    run_id,
                    topic,
                    bronze_dir,
                    batch_size,
                    max_messages,
                    allowed_lateness_seconds,
                    poll_timeout_seconds,
                    idle_timeout_seconds,
                    status,
                    started_at,
                    finished_at,
                    consumed_count,
                    bronze_row_count,
                    committed_count,
                    batch_count,
                    duplicate_count,
                    late_count,
                    dead_letter_count,
                    error_type,
                    error_message
                FROM stream_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise StreamStateError(f"could not read stream run {run_id}") from exc
        return None if row is None else _row_to_stream_run(row)

    def record_run_success(
        self,
        *,
        run_id: str,
        report: "ConsumeReport",
        finished_at: datetime,
    ) -> None:
        """Mark a running Dagster execution successful with its report counters."""
        _require_text(run_id, "run_id")
        finished_at_text = _timestamp_text(finished_at)
        try:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    UPDATE stream_runs
                    SET
                        status = 'succeeded',
                        finished_at = ?,
                        consumed_count = ?,
                        bronze_row_count = ?,
                        committed_count = ?,
                        batch_count = ?,
                        duplicate_count = ?,
                        late_count = ?,
                        dead_letter_count = ?,
                        error_type = NULL,
                        error_message = NULL
                    WHERE run_id = ? AND status = 'running'
                    """,
                    (
                        finished_at_text,
                        report.consumed_count,
                        report.bronze_row_count,
                        report.committed_count,
                        report.batch_count,
                        report.duplicate_count,
                        report.late_count,
                        report.dead_letter_count,
                        run_id,
                    ),
                )
                if cursor.rowcount != 1:
                    self._raise_run_transition_error(run_id)
        except StreamStateError:
            raise
        except sqlite3.Error as exc:
            raise StreamStateError(f"could not record successful stream run {run_id}") from exc

    def record_run_failure(
        self,
        *,
        run_id: str,
        error_type: str,
        error_message: str,
        finished_at: datetime,
    ) -> None:
        """Mark a running Dagster execution failed with terminal error details."""
        _require_text(run_id, "run_id")
        _require_text(error_type, "error_type")
        finished_at_text = _timestamp_text(finished_at)
        try:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    UPDATE stream_runs
                    SET
                        status = 'failed',
                        finished_at = ?,
                        consumed_count = NULL,
                        bronze_row_count = NULL,
                        committed_count = NULL,
                        batch_count = NULL,
                        duplicate_count = NULL,
                        late_count = NULL,
                        dead_letter_count = NULL,
                        error_type = ?,
                        error_message = ?
                    WHERE run_id = ? AND status = 'running'
                    """,
                    (finished_at_text, error_type, error_message, run_id),
                )
                if cursor.rowcount != 1:
                    self._raise_run_transition_error(run_id)
        except StreamStateError:
            raise
        except sqlite3.Error as exc:
            raise StreamStateError(f"could not record failed stream run {run_id}") from exc

    def _raise_run_transition_error(self, run_id: str) -> None:
        row = self._connection.execute(
            "SELECT status FROM stream_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise StreamStateError(f"stream run not found: {run_id}")
        raise StreamStateError(f"stream run is terminal: {run_id}")

    def record_bronze(
        self,
        *,
        topic: str,
        events: Sequence[TelemetryEvent],
    ) -> None:
        """Record Bronze outcomes and advance the topic watermark atomically."""
        _require_text(topic, "topic")
        if not events:
            raise ValueError("events must not be empty")

        try:
            with self._connection:
                batch_watermark = self.get_watermark(topic)
                pending: dict[str, str] = {}
                for event in events:
                    batch_watermark = self._record_bronze_event(
                        event,
                        pending=pending,
                        batch_watermark=batch_watermark,
                    )
                self._advance_watermark(topic, batch_watermark)
        except StreamStateError:
            raise
        except sqlite3.Error as exc:
            raise StreamStateError(f"could not record Bronze state for {topic}") from exc

    def _record_bronze_event(
        self,
        event: TelemetryEvent,
        *,
        pending: dict[str, str],
        batch_watermark: datetime | None,
    ) -> datetime | None:
        digest = telemetry_payload_sha256(event)
        previous_digest = pending.get(event.event_id)
        if previous_digest is not None:
            if previous_digest != digest:
                raise StreamStateError(f"event_id {event.event_id} has conflicting payloads")
            return batch_watermark

        existing = self.get_event(event.event_id)
        if existing is None:
            self._insert_bronze_event(event, digest)
        else:
            _validate_existing_bronze_event(existing, event.event_id, digest)

        pending[event.event_id] = digest
        return _latest_watermark(batch_watermark, event.ingestion_timestamp)

    def _insert_bronze_event(self, event: TelemetryEvent, digest: str) -> None:
        self._connection.execute(
            """
            INSERT INTO processed_events(
                event_id, payload_sha256, ingestion_timestamp, outcome, reason_code
            ) VALUES (?, ?, ?, 'bronze', NULL)
            """,
            (
                event.event_id,
                digest,
                _timestamp_text(event.ingestion_timestamp),
            ),
        )

    def _advance_watermark(self, topic: str, batch_watermark: datetime | None) -> None:
        if batch_watermark is None:
            return
        self._connection.execute(
            """
            INSERT INTO watermarks(topic, max_ingestion_timestamp)
            VALUES (?, ?)
            ON CONFLICT(topic) DO UPDATE SET
                max_ingestion_timestamp = excluded.max_ingestion_timestamp
            WHERE excluded.max_ingestion_timestamp > watermarks.max_ingestion_timestamp
            """,
            (topic, _timestamp_text(batch_watermark)),
        )

    def record_dead_letter(
        self,
        *,
        topic: str,
        event: TelemetryEvent,
        reason_code: str,
    ) -> None:
        """Record a valid event routed to DLQ without advancing the watermark."""
        _require_text(topic, "topic")
        _require_text(reason_code, "reason_code")
        digest = telemetry_payload_sha256(event)
        try:
            with self._connection:
                existing = self.get_event(event.event_id)
                if existing is not None:
                    if existing.payload_sha256 != digest:
                        raise StreamStateError(
                            f"event_id {event.event_id} has a conflicting payload"
                        )
                    if existing.outcome == "dead_letter" and existing.reason_code == reason_code:
                        return
                    raise StreamStateError(
                        f"event_id {event.event_id} already has outcome "
                        f"{existing.outcome}"
                    )
                self._connection.execute(
                    """
                    INSERT INTO processed_events(
                        event_id, payload_sha256, ingestion_timestamp, outcome, reason_code
                    ) VALUES (?, ?, ?, 'dead_letter', ?)
                    """,
                    (
                        event.event_id,
                        digest,
                        _timestamp_text(event.ingestion_timestamp),
                        reason_code,
                    ),
                )
        except StreamStateError:
            raise
        except sqlite3.Error as exc:
            raise StreamStateError(f"could not record DLQ state for {topic}") from exc

    def close(self) -> None:
        """Close the local SQLite connection; repeated closes are harmless."""
        if not self._closed:
            self._connection.close()
            self._closed = True


def _row_to_event_state(row: sqlite3.Row) -> ProcessedEventState:
    raw_outcome = cast(str, row["outcome"])
    if raw_outcome not in {"bronze", "dead_letter"}:
        raise StreamStateError(f"invalid stored event outcome: {raw_outcome}")
    return ProcessedEventState(
        event_id=cast(str, row["event_id"]),
        payload_sha256=cast(str, row["payload_sha256"]),
        ingestion_timestamp=_parse_timestamp(cast(str, row["ingestion_timestamp"])),
        outcome=cast(EventOutcome, raw_outcome),
        reason_code=cast(str | None, row["reason_code"]),
    )


def _row_to_stream_run(row: sqlite3.Row) -> StreamRun:
    raw_status = cast(str, row["status"])
    if raw_status not in {"running", "succeeded", "failed"}:
        raise StreamStateError(f"invalid stored stream run status: {raw_status}")
    raw_finished_at = cast(str | None, row["finished_at"])
    return StreamRun(
        run_id=cast(str, row["run_id"]),
        topic=cast(str, row["topic"]),
        bronze_dir=Path(cast(str, row["bronze_dir"])),
        batch_size=cast(int, row["batch_size"]),
        max_messages=cast(int, row["max_messages"]),
        allowed_lateness_seconds=cast(int, row["allowed_lateness_seconds"]),
        poll_timeout_seconds=cast(float, row["poll_timeout_seconds"]),
        idle_timeout_seconds=cast(float, row["idle_timeout_seconds"]),
        status=cast(StreamRunStatus, raw_status),
        started_at=_parse_timestamp(cast(str, row["started_at"])),
        finished_at=None if raw_finished_at is None else _parse_timestamp(raw_finished_at),
        consumed_count=cast(int | None, row["consumed_count"]),
        bronze_row_count=cast(int | None, row["bronze_row_count"]),
        committed_count=cast(int | None, row["committed_count"]),
        batch_count=cast(int | None, row["batch_count"]),
        duplicate_count=cast(int | None, row["duplicate_count"]),
        late_count=cast(int | None, row["late_count"]),
        dead_letter_count=cast(int | None, row["dead_letter_count"]),
        error_type=cast(str | None, row["error_type"]),
        error_message=cast(str | None, row["error_message"]),
    )


def _validate_existing_bronze_event(
    existing: ProcessedEventState,
    event_id: str,
    digest: str,
) -> None:
    if existing.payload_sha256 != digest:
        raise StreamStateError(f"event_id {event_id} has a conflicting payload")
    if existing.outcome != "bronze":
        raise StreamStateError(f"event_id {event_id} already has outcome {existing.outcome}")


def _latest_watermark(current: datetime | None, candidate: datetime) -> datetime:
    if current is None or candidate > current:
        return candidate
    return current


def _timestamp_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StreamStateError("stored timestamp is not valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise StreamStateError("stored timestamp must use UTC")
    return parsed


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_stream_run_inputs(inputs: StreamRunInputs) -> None:
    _require_text(inputs.topic, "topic")
    _require_text(str(inputs.bronze_dir), "bronze_dir")
    if inputs.batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    if inputs.max_messages <= 0:
        raise ValueError("max_messages must be greater than zero")
    if inputs.allowed_lateness_seconds < 0:
        raise ValueError("allowed_lateness_seconds must not be negative")
    if inputs.poll_timeout_seconds < 0:
        raise ValueError("poll_timeout_seconds must not be negative")
    if inputs.idle_timeout_seconds < 0:
        raise ValueError("idle_timeout_seconds must not be negative")
