"""Manual-commit consumption of telemetry into immutable Bronze batches."""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from portflow.domain.models import TelemetryEvent
from portflow.ingestion.postgres_to_bronze import (
    StreamBronzeWriteResult,
    write_telemetry_bronze_batch,
)
from portflow.streaming.codec import Header, decode_telemetry_event
from portflow.streaming.config import StreamingConfig, consumer_properties


class ConsumerMessage(Protocol):
    def value(self) -> bytes | None:
        pass

    def headers(self) -> Sequence[Header] | None:
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
    """Raised when polling or Bronze publication cannot complete safely."""


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


def consume_telemetry_stream(
    consumer: ConsumerClient,
    *,
    topic: str,
    bronze_dir: Path,
    run_id: str,
    batch_size: int,
    max_messages: int,
    writer: BronzeWriter = write_telemetry_bronze_batch,
    poll_timeout_seconds: float = 1.0,
    idle_timeout_seconds: float = 30.0,
) -> ConsumeReport:
    """Consume, publish, and synchronously commit bounded telemetry batches."""
    if not topic:
        raise ValueError("topic must not be empty")
    if not run_id:
        raise ValueError("run_id must not be empty")
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    if max_messages <= 0:
        raise ValueError("max_messages must be greater than zero")
    if poll_timeout_seconds < 0:
        raise ValueError("poll_timeout_seconds must not be negative")
    if idle_timeout_seconds < 0:
        raise ValueError("idle_timeout_seconds must not be negative")

    pending: list[tuple[TelemetryEvent, ConsumerMessage]] = []
    consumed_count = 0
    bronze_row_count = 0
    committed_count = 0
    batch_count = 0
    last_activity = time.monotonic()

    try:
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
            event = decode_telemetry_event(message.value(), message.headers())
            pending.append((event, message))
            consumed_count += 1

            if len(pending) >= batch_size or consumed_count >= max_messages:
                events = [event for event, _message in pending]
                result = writer(events, bronze_dir=bronze_dir, run_id=run_id)
                consumer.commit(message=pending[-1][1], asynchronous=False)
                bronze_row_count += result.row_count
                committed_count += 1
                batch_count += 1
                pending.clear()

        return ConsumeReport(
            consumed_count=consumed_count,
            bronze_row_count=bronze_row_count,
            committed_count=committed_count,
            batch_count=batch_count,
        )
    finally:
        consumer.close()


def create_consumer(config: StreamingConfig) -> ConsumerClient:
    """Construct the concrete Confluent consumer only when requested."""
    from confluent_kafka import Consumer  # type: ignore[import-not-found]

    return cast(ConsumerClient, Consumer(consumer_properties(config)))


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
