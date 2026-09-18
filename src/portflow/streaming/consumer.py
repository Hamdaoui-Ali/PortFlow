"""Manual-commit consumption of telemetry into immutable Bronze batches."""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol, cast

from portflow.domain.models import TelemetryEvent
from portflow.ingestion.postgres_to_bronze import (
    StreamBronzeWriteResult,
    write_telemetry_bronze_batch,
)
from portflow.streaming.codec import (
    Header,
    StreamValidationError,
    decode_telemetry_event,
    telemetry_payload_sha256,
)
from portflow.streaming.config import StreamingConfig, consumer_properties
from portflow.streaming.dead_letter import (
    DeadLetterReasonCode,
    DeadLetterRecord,
    publish_dead_letters,
)
from portflow.streaming.producer import ProducerClient
from portflow.streaming.state import StreamStateStore


class ConsumerMessage(Protocol):
    def value(self) -> bytes | None:
        pass

    def headers(self) -> Sequence[Header] | None:
        pass

    def key(self) -> bytes | None:
        pass

    def partition(self) -> int:
        pass

    def offset(self) -> int:
        pass


class ConsumerClient(Protocol):
    def subscribe(self, topics: Sequence[str]) -> None:
        pass

    def poll(self, timeout: float) -> ConsumerMessage | None:
        pass

    def commit(self, *, message: ConsumerMessage, asynchronous: bool) -> None:
        pass

    def close(self) -> None:
        pass


class StreamConsumerError(RuntimeError):
    """Raised when polling or stream publication cannot complete safely."""


class BronzeWriter(Protocol):
    def __call__(
        self,
        events: Sequence[TelemetryEvent],
        *,
        bronze_dir: Path,
        run_id: str,
    ) -> StreamBronzeWriteResult:
        pass


@dataclass(frozen=True, slots=True)
class ConsumeReport:
    """Summary of one bounded stream consumption run."""

    consumed_count: int
    bronze_row_count: int
    committed_count: int
    batch_count: int
    duplicate_count: int = 0
    late_count: int = 0
    dead_letter_count: int = 0


@dataclass(frozen=True, slots=True)
class _DeadLetterCandidate:
    record: DeadLetterRecord
    event: TelemetryEvent | None
    record_in_state: bool


def consume_telemetry_stream(
    consumer: ConsumerClient,
    *,
    topic: str,
    bronze_dir: Path,
    run_id: str,
    batch_size: int,
    max_messages: int,
    writer: BronzeWriter = write_telemetry_bronze_batch,
    dead_letter_producer: ProducerClient | None = None,
    dead_letter_topic: str | None = None,
    allowed_lateness_seconds: int = 300,
    state_store: StreamStateStore | None = None,
    poll_timeout_seconds: float = 1.0,
    idle_timeout_seconds: float = 30.0,
) -> ConsumeReport:
    """Consume bounded telemetry batches with durable classification and commits."""
    if not topic.strip():
        raise ValueError("topic must not be empty")
    if not run_id.strip():
        raise ValueError("run_id must not be empty")
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    if max_messages <= 0:
        raise ValueError("max_messages must be greater than zero")
    if allowed_lateness_seconds < 0:
        raise ValueError("allowed_lateness_seconds must not be negative")
    if poll_timeout_seconds < 0:
        raise ValueError("poll_timeout_seconds must not be negative")
    if idle_timeout_seconds < 0:
        raise ValueError("idle_timeout_seconds must not be negative")

    owned_state_store = state_store is None
    active_state_store = state_store
    processing_error: BaseException | None = None

    try:
        if active_state_store is None:
            active_state_store = StreamStateStore(bronze_dir / ".stream-state.sqlite3")

        pending_messages: list[ConsumerMessage] = []
        accepted_events: list[TelemetryEvent] = []
        dead_letter_candidates: list[_DeadLetterCandidate] = []
        pending_digests: dict[str, str] = {}
        batch_watermark: datetime | None = None
        consumed_count = 0
        bronze_row_count = 0
        committed_count = 0
        batch_count = 0
        duplicate_count = 0
        late_count = 0
        dead_letter_count = 0
        last_activity = time.monotonic()

        consumer.subscribe([topic])
        while consumed_count < max_messages:
            try:
                message = consumer.poll(poll_timeout_seconds)
            except Exception as exc:
                raise StreamConsumerError("consumer poll failed") from exc

            if message is None:
                _raise_if_idle(last_activity, idle_timeout_seconds)
                continue

            message_error = _message_error(message)
            if message_error is not None:
                if _is_partition_eof(message_error):
                    _raise_if_idle(last_activity, idle_timeout_seconds)
                    continue
                raise StreamConsumerError(f"consumer poll failed: {message_error}")

            last_activity = time.monotonic()
            if not pending_messages:
                batch_watermark = active_state_store.get_watermark(topic)
            pending_messages.append(message)
            consumed_count += 1

            classification = _classify_message(
                message,
                topic=topic,
                run_id=run_id,
                watermark=batch_watermark,
                allowed_lateness_seconds=allowed_lateness_seconds,
                state_store=active_state_store,
                pending_digests=pending_digests,
            )
            if classification.accepted_event is not None:
                accepted_events.append(classification.accepted_event)
            if classification.dead_letter is not None:
                dead_letter_candidates.append(classification.dead_letter)
            duplicate_count += classification.duplicate_count
            late_count += classification.late_count

            if len(pending_messages) >= batch_size or consumed_count >= max_messages:
                if dead_letter_candidates and (
                    dead_letter_producer is None
                    or dead_letter_topic is None
                    or not dead_letter_topic.strip()
                ):
                    raise StreamConsumerError(
                        "dead-letter producer and topic are required for rejected messages"
                    )

                if accepted_events:
                    accepted_batch = tuple(accepted_events)
                    result = writer(
                        accepted_batch,
                        bronze_dir=bronze_dir,
                        run_id=run_id,
                    )
                    active_state_store.record_bronze(
                        topic=topic,
                        events=accepted_batch,
                    )
                    bronze_row_count += result.row_count

                if dead_letter_candidates:
                    assert dead_letter_producer is not None
                    assert dead_letter_topic is not None
                    dead_letter_count += publish_dead_letters(
                        [candidate.record for candidate in dead_letter_candidates],
                        producer=dead_letter_producer,
                        topic=dead_letter_topic,
                    )
                    for candidate in dead_letter_candidates:
                        if candidate.record_in_state and candidate.event is not None:
                            active_state_store.record_dead_letter(
                                topic=topic,
                                event=candidate.event,
                                reason_code=candidate.record.reason_code,
                            )

                consumer.commit(message=pending_messages[-1], asynchronous=False)
                committed_count += 1
                batch_count += 1
                pending_messages.clear()
                accepted_events.clear()
                dead_letter_candidates.clear()
                pending_digests.clear()
                batch_watermark = None

        return ConsumeReport(
            consumed_count=consumed_count,
            bronze_row_count=bronze_row_count,
            committed_count=committed_count,
            batch_count=batch_count,
            duplicate_count=duplicate_count,
            late_count=late_count,
            dead_letter_count=dead_letter_count,
        )
    except BaseException as exc:
        processing_error = exc
        raise
    finally:
        cleanup_error: BaseException | None = None
        try:
            consumer.close()
        except BaseException as exc:
            cleanup_error = exc
        if owned_state_store and active_state_store is not None:
            try:
                active_state_store.close()
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        if cleanup_error is not None and processing_error is None:
            raise cleanup_error


def create_consumer(config: StreamingConfig) -> ConsumerClient:
    """Construct the concrete Confluent consumer only when requested."""
    from confluent_kafka import Consumer

    return cast(ConsumerClient, Consumer(consumer_properties(config)))


@dataclass(frozen=True, slots=True)
class _MessageClassification:
    accepted_event: TelemetryEvent | None = None
    dead_letter: _DeadLetterCandidate | None = None
    duplicate_count: int = 0
    late_count: int = 0


def _classify_message(
    message: ConsumerMessage,
    *,
    topic: str,
    run_id: str,
    watermark: datetime | None,
    allowed_lateness_seconds: int,
    state_store: StreamStateStore,
    pending_digests: dict[str, str],
) -> _MessageClassification:
    payload = message.value()
    headers = message.headers()
    try:
        event = decode_telemetry_event(payload, headers)
    except StreamValidationError as exc:
        return _MessageClassification(
            dead_letter=_make_dead_letter(
                message,
                topic=topic,
                run_id=run_id,
                payload=payload,
                headers=headers,
                reason_code="invalid_telemetry",
                reason=str(exc),
            )
        )

    digest = telemetry_payload_sha256(event)
    previous_digest = pending_digests.get(event.event_id)
    if previous_digest is not None:
        if previous_digest == digest:
            return _MessageClassification(duplicate_count=1)
        return _MessageClassification(
            dead_letter=_make_dead_letter(
                message,
                topic=topic,
                run_id=run_id,
                payload=payload,
                headers=headers,
                reason_code="duplicate_conflict",
                reason=f"event_id {event.event_id} was reused with a different payload",
            )
        )

    pending_digests[event.event_id] = digest
    existing = state_store.get_event(event.event_id)
    if existing is not None:
        if existing.payload_sha256 == digest:
            return _MessageClassification(duplicate_count=1)
        return _MessageClassification(
            dead_letter=_make_dead_letter(
                message,
                topic=topic,
                run_id=run_id,
                payload=payload,
                headers=headers,
                reason_code="duplicate_conflict",
                reason=f"event_id {event.event_id} was reused with a different payload",
            )
        )

    if watermark is not None and event.ingestion_timestamp < watermark - timedelta(
        seconds=allowed_lateness_seconds
    ):
        return _MessageClassification(
            dead_letter=_make_dead_letter(
                message,
                topic=topic,
                run_id=run_id,
                payload=payload,
                headers=headers,
                reason_code="late_event",
                reason=(
                    f"ingestion timestamp {event.ingestion_timestamp.isoformat()} "
                    f"is older than watermark {watermark.isoformat()} by more than "
                    f"{allowed_lateness_seconds} seconds"
                ),
                event=event,
                record_in_state=True,
            ),
            late_count=1,
        )

    return _MessageClassification(accepted_event=event)


def _make_dead_letter(
    message: ConsumerMessage,
    *,
    topic: str,
    run_id: str,
    payload: bytes | None,
    headers: Sequence[Header] | None,
    reason_code: DeadLetterReasonCode,
    reason: str,
    event: TelemetryEvent | None = None,
    record_in_state: bool = False,
) -> _DeadLetterCandidate:
    return _DeadLetterCandidate(
        record=DeadLetterRecord(
            source_topic=topic,
            source_partition=_message_partition(message),
            source_offset=message.offset(),
            source_key=_message_key(message),
            source_value=payload,
            source_headers=headers,
            reason_code=reason_code,
            reason=reason,
            run_id=run_id,
        ),
        event=event,
        record_in_state=record_in_state,
    )


def _message_key(message: ConsumerMessage) -> bytes | None:
    key_method = getattr(message, "key", None)
    if not callable(key_method):
        return None
    return cast(Callable[[], bytes | None], key_method)()


def _message_partition(message: ConsumerMessage) -> int:
    partition_method = getattr(message, "partition", None)
    if not callable(partition_method):
        return 0
    return cast(Callable[[], int], partition_method)()


def _raise_if_idle(last_activity: float, idle_timeout_seconds: float) -> None:
    if time.monotonic() - last_activity >= idle_timeout_seconds:
        raise StreamConsumerError("consumer idle timeout exceeded")


def _message_error(message: ConsumerMessage) -> object | None:
    error_method = getattr(message, "error", None)
    if not callable(error_method):
        return None
    return cast(Callable[[], object | None], error_method)()


def _is_partition_eof(error: object) -> bool:
    code_accessor = getattr(error, "code", None)
    code = (
        cast(Callable[[], object], code_accessor)()
        if callable(code_accessor)
        else code_accessor
    )
    if code is None:
        return False

    try:
        from confluent_kafka import KafkaError
    except ImportError:
        return False
    return code == getattr(KafkaError, "_PARTITION_EOF", None)
