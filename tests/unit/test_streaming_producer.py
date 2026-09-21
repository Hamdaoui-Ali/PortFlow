import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from types import ModuleType

import pytest

from portflow.domain.models import EquipmentState, TelemetryEvent
from portflow.streaming.codec import encode_telemetry_event, telemetry_headers
from portflow.streaming.config import StreamingConfig
from portflow.streaming.producer import (
    ProducerDeliveryError,
    PublishReport,
    create_producer,
    publish_telemetry_events,
)


def valid_event() -> TelemetryEvent:
    return TelemetryEvent(
        event_id="evt-000042-000001",
        schema_version=1,
        equipment_id="QC-001",
        terminal_id="TM-001",
        event_timestamp=datetime(2026, 9, 2, tzinfo=UTC),
        ingestion_timestamp=datetime(2026, 9, 2, 0, 0, 2, tzinfo=UTC),
        state=EquipmentState.ACTIVE,
        available=True,
        load_percent=50.0,
        temperature_c=55.0,
    )


@dataclass(frozen=True, slots=True)
class ProduceCall:
    topic: str
    key: bytes
    value: bytes
    headers: list[tuple[str, bytes]]


class FakeProducer:
    def __init__(self, delivery_error: object | None = None, remaining: int = 0) -> None:
        self.calls: list[ProduceCall] = []
        self.delivery_error = delivery_error
        self.remaining = remaining
        self.poll_calls: list[float] = []
        self.flush_calls: list[float] = []

    def produce(
        self,
        topic: str,
        *,
        key: bytes,
        value: bytes,
        headers: list[tuple[str, bytes]],
        callback: Callable[[object | None, object], None],
    ) -> None:
        self.calls.append(ProduceCall(topic, key, value, headers))
        callback(self.delivery_error, object())

    def poll(self, timeout: float) -> int:
        self.poll_calls.append(timeout)
        return 0

    def flush(self, timeout: float) -> int:
        self.flush_calls.append(timeout)
        return self.remaining


def test_publish_uses_event_id_key_topic_and_headers() -> None:
    producer = FakeProducer()
    events = [valid_event()]

    report = publish_telemetry_events(
        events,
        producer=producer,
        topic="portflow.telemetry",
    )

    assert report == PublishReport(topic="portflow.telemetry", published_count=1)
    assert producer.calls[0].topic == "portflow.telemetry"
    assert producer.calls[0].key == b"evt-000042-000001"
    assert producer.calls[0].value == encode_telemetry_event(events[0])
    assert producer.calls[0].headers == list(telemetry_headers())
    assert producer.poll_calls == [0.0]
    assert producer.flush_calls == [10.0]


def test_publish_surfaces_delivery_error_without_success_report() -> None:
    producer = FakeProducer(delivery_error="broker rejected record")

    with pytest.raises(ProducerDeliveryError, match="broker rejected record"):
        publish_telemetry_events([valid_event()], producer=producer, topic="portflow.telemetry")


def test_publish_surfaces_unflushed_records() -> None:
    producer = FakeProducer(remaining=1)

    with pytest.raises(ProducerDeliveryError, match="1"):
        publish_telemetry_events([valid_event()], producer=producer, topic="portflow.telemetry")


def test_publish_rejects_negative_flush_timeout() -> None:
    with pytest.raises(ValueError, match="flush_timeout"):
        publish_telemetry_events(
            [valid_event()],
            producer=FakeProducer(),
            topic="portflow.telemetry",
            flush_timeout=-1.0,
        )


def test_create_producer_uses_edge_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, dict[str, str]] = {}

    class FakeKafkaProducer:
        def __init__(self, properties: dict[str, str]) -> None:
            created["properties"] = properties

    kafka_module = ModuleType("confluent_kafka")
    kafka_module.Producer = FakeKafkaProducer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "confluent_kafka", kafka_module)

    config = StreamingConfig(
        brokers="redpanda:9092",
        topic="portflow.telemetry",
        group_id="portflow-bronze",
        batch_size=50,
        dlq_topic="portflow.telemetry.dlq",
        allowed_lateness_seconds=300,
    )

    producer = create_producer(config)

    assert isinstance(producer, FakeKafkaProducer)
    assert created["properties"] == {
        "bootstrap.servers": "redpanda:9092",
        "client.id": "portflow-producer",
        "enable.idempotence": "true",
        "acks": "all",
    }
