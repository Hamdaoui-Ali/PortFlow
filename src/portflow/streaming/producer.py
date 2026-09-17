"""Deterministic telemetry publishing behind a small producer protocol."""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from portflow.domain.models import TelemetryEvent
from portflow.streaming.codec import encode_telemetry_event, telemetry_headers
from portflow.streaming.config import StreamingConfig, producer_properties

DeliveryCallback = Callable[[object | None, object], None]


class ProducerClient(Protocol):
    def produce(
        self,
        topic: str,
        *,
        key: bytes,
        value: bytes,
        headers: Sequence[tuple[str, bytes]],
        callback: DeliveryCallback,
    ) -> None:
        pass

    def poll(self, timeout: float) -> int:
        pass

    def flush(self, timeout: float) -> int:
        pass


class ProducerDeliveryError(RuntimeError):
    """Raised when Redpanda does not acknowledge every produced event."""


@dataclass(frozen=True, slots=True)
class PublishReport:
    """Summary of a completed telemetry publish operation."""

    topic: str
    published_count: int


def publish_telemetry_events(
    events: Iterable[TelemetryEvent],
    *,
    producer: ProducerClient,
    topic: str,
    flush_timeout: float = 10.0,
) -> PublishReport:
    """Publish telemetry events and require every delivery to be acknowledged."""
    if flush_timeout < 0:
        raise ValueError("flush_timeout must not be negative")

    delivery_errors: list[object] = []

    def on_delivery(error: object | None, _message: object) -> None:
        if error is not None:
            delivery_errors.append(error)

    published_count = 0
    for event in events:
        producer.produce(
            topic,
            key=event.event_id.encode("utf-8"),
            value=encode_telemetry_event(event),
            headers=list(telemetry_headers()),
            callback=on_delivery,
        )
        producer.poll(0.0)
        published_count += 1

    remaining_count = producer.flush(flush_timeout)
    if delivery_errors:
        raise ProducerDeliveryError(f"delivery failed: {delivery_errors[0]}")
    if remaining_count != 0:
        raise ProducerDeliveryError(f"{remaining_count} produced records remain undelivered")

    return PublishReport(topic=topic, published_count=published_count)


def create_producer(config: StreamingConfig) -> ProducerClient:
    """Construct the concrete Confluent producer only when requested."""
    from confluent_kafka import Producer  # type: ignore[import-not-found]

    return cast(ProducerClient, Producer(producer_properties(config)))
