"""Canonical dead-letter envelopes for rejected telemetry stream records."""

import base64
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from portflow.streaming.codec import Header
from portflow.streaming.producer import ProducerClient, ProducerDeliveryError

DeadLetterReasonCode = Literal[
    "invalid_telemetry",
    "late_event",
    "duplicate_conflict",
]

_REASON_CODES = frozenset(
    {"invalid_telemetry", "late_event", "duplicate_conflict"}
)


@dataclass(frozen=True, slots=True)
class DeadLetterRecord:
    """Transport-neutral source record and reason for a DLQ decision."""

    source_topic: str
    source_partition: int
    source_offset: int
    source_key: bytes | None
    source_value: bytes | None
    source_headers: Sequence[Header] | None
    reason_code: DeadLetterReasonCode
    reason: str
    run_id: str


def encode_dead_letter(record: DeadLetterRecord) -> bytes:
    """Encode a dead-letter record as deterministic, lossless UTF-8 JSON."""
    _validate_record(record)
    envelope = {
        "reason": record.reason,
        "reason_code": record.reason_code,
        "run_id": record.run_id,
        "schema_version": 1,
        "source_headers": _encode_headers(record.source_headers),
        "source_key_base64": _encode_binary(record.source_key),
        "source_offset": record.source_offset,
        "source_partition": record.source_partition,
        "source_topic": record.source_topic,
        "source_value_base64": _encode_binary(record.source_value),
    }
    return json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def publish_dead_letters(
    records: Sequence[DeadLetterRecord],
    *,
    producer: ProducerClient,
    topic: str,
    flush_timeout: float = 10.0,
) -> int:
    """Publish canonical DLQ envelopes and require every delivery to finish."""
    if not topic.strip():
        raise ValueError("topic must not be empty")
    if flush_timeout < 0:
        raise ValueError("flush_timeout must not be negative")

    prepared = [
        (
            record,
            encode_dead_letter(record),
            record.source_key
            if record.source_key is not None
            else f"{record.source_topic}:{record.source_partition}:{record.source_offset}".encode(),
        )
        for record in records
    ]

    delivery_errors: list[object] = []

    def on_delivery(error: object | None, _message: object) -> None:
        if error is not None:
            delivery_errors.append(error)

    for _record, payload, key in prepared:
        producer.produce(
            topic,
            key=key,
            value=payload,
            headers=[
                ("portflow-dead-letter-reason", _record.reason_code.encode("utf-8")),
                ("portflow-schema-version", b"1"),
            ],
            callback=on_delivery,
        )
        producer.poll(0.0)

    remaining_count = producer.flush(flush_timeout)
    if delivery_errors:
        raise ProducerDeliveryError(f"delivery failed: {delivery_errors[0]}")
    if remaining_count != 0:
        raise ProducerDeliveryError(f"{remaining_count} produced records remain undelivered")

    return len(prepared)


def _validate_record(record: DeadLetterRecord) -> None:
    _require_text(record.source_topic, "source_topic")
    _require_text(record.reason, "reason")
    _require_text(record.run_id, "run_id")
    if record.reason_code not in _REASON_CODES:
        raise ValueError(f"unsupported dead-letter reason code: {record.reason_code}")
    if record.source_partition < 0:
        raise ValueError("source_partition must not be negative")
    if record.source_offset < 0:
        raise ValueError("source_offset must not be negative")
    if record.source_headers is not None:
        for name, _value in record.source_headers:
            _require_text(name, "source header name")


def _encode_binary(value: bytes | None) -> str | None:
    return None if value is None else base64.b64encode(value).decode("ascii")


def _encode_headers(
    headers: Sequence[Header] | None,
) -> list[dict[str, str | None]] | None:
    if headers is None:
        return None
    return [
        {"name": name, "value_base64": _encode_binary(value)}
        for name, value in headers
    ]


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
