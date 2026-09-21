import base64
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import pytest

from portflow.streaming.codec import Header
from portflow.streaming.dead_letter import (
    DeadLetterRecord,
    encode_dead_letter,
    publish_dead_letters,
)
from portflow.streaming.producer import ProducerDeliveryError


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
        headers: Sequence[tuple[str, bytes]],
        callback: Callable[[object | None, object], None],
    ) -> None:
        self.calls.append(ProduceCall(topic, key, value, list(headers)))
        callback(self.delivery_error, object())

    def poll(self, timeout: float) -> int:
        self.poll_calls.append(timeout)
        return 0

    def flush(self, timeout: float) -> int:
        self.flush_calls.append(timeout)
        return self.remaining


def dead_letter_record(
    *,
    source_key: bytes | None = b"evt-000042-000001",
    source_value: bytes | None = b"{\"ok\":false}",
    source_headers: Sequence[Header] | None = (
        ("portflow-event-type", b"telemetry"),
        ("trace", None),
    ),
) -> DeadLetterRecord:
    return DeadLetterRecord(
        source_topic="portflow.telemetry",
        source_partition=0,
        source_offset=17,
        source_key=source_key,
        source_value=source_value,
        source_headers=source_headers,
        reason_code="invalid_telemetry",
        reason="Capteur en panne — arrêt",
        run_id="stream-run-000042",
    )


def test_encode_dead_letter_is_canonical_and_reversible() -> None:
    record = dead_letter_record(source_value=b"\x00\xff")

    encoded = encode_dead_letter(record)
    expected = {
        "reason": "Capteur en panne — arrêt",
        "reason_code": "invalid_telemetry",
        "run_id": "stream-run-000042",
        "schema_version": 1,
        "source_headers": [
            {"name": "portflow-event-type", "value_base64": "dGVsZW1ldHJ5"},
            {"name": "trace", "value_base64": None},
        ],
        "source_key_base64": base64.b64encode(b"evt-000042-000001").decode("ascii"),
        "source_offset": 17,
        "source_partition": 0,
        "source_topic": "portflow.telemetry",
        "source_value_base64": "AP8=",
    }

    assert encoded == json.dumps(
        expected,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    assert json.loads(encoded) == expected


def test_publish_dead_letters_preserves_key_and_reason_header() -> None:
    producer = FakeProducer()
    record = dead_letter_record()

    published = publish_dead_letters(
        [record],
        producer=producer,
        topic="portflow.telemetry.dlq",
    )

    assert published == 1
    assert producer.calls[0].topic == "portflow.telemetry.dlq"
    assert producer.calls[0].key == b"evt-000042-000001"
    assert producer.calls[0].headers == [
        ("portflow-dead-letter-reason", b"invalid_telemetry"),
        ("portflow-schema-version", b"1"),
    ]
    assert producer.poll_calls == [0.0]
    assert producer.flush_calls == [10.0]


def test_publish_dead_letters_uses_source_location_key_when_key_is_missing() -> None:
    producer = FakeProducer()
    record = dead_letter_record(source_key=None)

    publish_dead_letters([record], producer=producer, topic="portflow.telemetry.dlq")

    assert producer.calls[0].key == b"portflow.telemetry:0:17"


def test_publish_dead_letters_surfaces_delivery_error() -> None:
    producer = FakeProducer(delivery_error="broker rejected record")
    record = dead_letter_record()

    with pytest.raises(ProducerDeliveryError, match="broker rejected record"):
        publish_dead_letters(
            [record],
            producer=producer,
            topic="portflow.telemetry.dlq",
        )


def test_publish_dead_letters_surfaces_unflushed_records() -> None:
    producer = FakeProducer(remaining=1)
    record = dead_letter_record()

    with pytest.raises(ProducerDeliveryError, match="1"):
        publish_dead_letters(
            [record],
            producer=producer,
            topic="portflow.telemetry.dlq",
        )


def test_publish_dead_letters_validates_all_records_before_producing() -> None:
    producer = FakeProducer()
    invalid = dead_letter_record()
    invalid = DeadLetterRecord(
        source_topic=invalid.source_topic,
        source_partition=invalid.source_partition,
        source_offset=invalid.source_offset,
        source_key=invalid.source_key,
        source_value=invalid.source_value,
        source_headers=invalid.source_headers,
        reason_code=invalid.reason_code,
        reason=invalid.reason,
        run_id="",
    )
    valid = dead_letter_record()

    with pytest.raises(ValueError, match="run_id"):
        publish_dead_letters(
            [valid, invalid],
            producer=producer,
            topic="portflow.telemetry.dlq",
        )

    assert producer.calls == []
