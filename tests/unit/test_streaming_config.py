import pytest

from portflow.streaming.config import (
    StreamingConfig,
    consumer_properties,
    producer_properties,
)


def test_defaults_are_safe_for_local_compose() -> None:
    config = StreamingConfig.from_env({})

    assert config == StreamingConfig(
        brokers="localhost:19092",
        topic="portflow.telemetry",
        group_id="portflow-bronze",
        batch_size=50,
        dlq_topic="portflow.telemetry.dlq",
        allowed_lateness_seconds=300,
    )
    assert producer_properties(config) == {
        "bootstrap.servers": "localhost:19092",
        "client.id": "portflow-producer",
        "enable.idempotence": "true",
        "acks": "all",
    }
    assert consumer_properties(config) == {
        "bootstrap.servers": "localhost:19092",
        "group.id": "portflow-bronze",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": "false",
    }


@pytest.mark.parametrize(
    "env",
    [
        {"PORTFLOW_REDPANDA_BROKERS": ""},
        {"PORTFLOW_REDPANDA_TOPIC": ""},
        {"PORTFLOW_REDPANDA_GROUP": ""},
        {"PORTFLOW_REDPANDA_DLQ_TOPIC": ""},
        {
            "PORTFLOW_REDPANDA_TOPIC": "same",
            "PORTFLOW_REDPANDA_DLQ_TOPIC": "same",
        },
        {"PORTFLOW_STREAM_BATCH_SIZE": "0"},
        {"PORTFLOW_STREAM_BATCH_SIZE": "not-an-int"},
        {"PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS": "not-an-int"},
        {"PORTFLOW_STREAM_ALLOWED_LATENESS_SECONDS": "-1"},
    ],
)
def test_rejects_invalid_values(env: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        StreamingConfig.from_env(env)
