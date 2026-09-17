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

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "StreamingConfig":
        source = os.environ if env is None else env
        brokers = _required_value(source, "PORTFLOW_REDPANDA_BROKERS", "localhost:19092")
        topic = _required_value(source, "PORTFLOW_REDPANDA_TOPIC", "portflow.telemetry")
        group_id = _required_value(source, "PORTFLOW_REDPANDA_GROUP", "portflow-bronze")
        raw_batch_size = source.get("PORTFLOW_STREAM_BATCH_SIZE", "50").strip()

        try:
            batch_size = int(raw_batch_size)
        except ValueError as exc:
            raise ValueError("PORTFLOW_STREAM_BATCH_SIZE must be an integer") from exc
        if batch_size < 1:
            raise ValueError("PORTFLOW_STREAM_BATCH_SIZE must be at least one")

        return cls(
            brokers=brokers,
            topic=topic,
            group_id=group_id,
            batch_size=batch_size,
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
