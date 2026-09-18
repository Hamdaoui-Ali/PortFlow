"""Configuration shared by PortFlow's local streaming clients."""

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StreamingConfig:
    brokers: str
    topic: str
    group_id: str
    batch_size: int
    dlq_topic: str
    allowed_lateness_seconds: int

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "StreamingConfig":
        source = os.environ if env is None else env
        brokers = _required_value(source, "PORTFLOW_REDPANDA_BROKERS", "localhost:19092")
        topic = _required_value(source, "PORTFLOW_REDPANDA_TOPIC", "portflow.telemetry")
        group_id = _required_value(source, "PORTFLOW_REDPANDA_GROUP", "portflow-bronze")
        dlq_topic = _required_value(
            source,
            "PORTFLOW_REDPANDA_DLQ_TOPIC",
            "portflow.telemetry.dlq",
        )
        if dlq_topic == topic:
            raise ValueError("PORTFLOW_REDPANDA_DLQ_TOPIC must differ from the source topic")
        raw_batch_size = source.get("PORTFLOW_STREAM_BATCH_SIZE", "50").strip()
        raw_allowed_lateness = source.get(
            "PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS",
            "300",
        ).strip()

        try:
            batch_size = int(raw_batch_size)
        except ValueError as exc:
            raise ValueError("PORTFLOW_STREAM_BATCH_SIZE must be an integer") from exc
        if batch_size < 1:
            raise ValueError("PORTFLOW_STREAM_BATCH_SIZE must be at least one")

        try:
            allowed_lateness_seconds = int(raw_allowed_lateness)
        except ValueError as exc:
            raise ValueError(
                "PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS must be an integer"
            ) from exc
        if allowed_lateness_seconds < 0:
            raise ValueError(
                "PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS must not be negative"
            )

        return cls(
            brokers=brokers,
            topic=topic,
            group_id=group_id,
            batch_size=batch_size,
            dlq_topic=dlq_topic,
            allowed_lateness_seconds=allowed_lateness_seconds,
        )


def producer_properties(config: StreamingConfig) -> dict[str, str]:
    return {
        "bootstrap.servers": config.brokers,
        "client.id": "portflow-producer",
        "enable.idempotence": "true",
        "acks": "all",
    }


def consumer_properties(config: StreamingConfig) -> dict[str, str]:
    return {
        "bootstrap.servers": config.brokers,
        "group.id": config.group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": "false",
    }


def _required_value(source: Mapping[str, str], name: str, default: str) -> str:
    value = source.get(name, default).strip()
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value
