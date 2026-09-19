from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("dagster")

from portflow.orchestration.streaming import (
    StreamConsumerJobConfig,
    execute_stream_consumer_run,
    stream_consumer_job,
)
from portflow.streaming.config import StreamingConfig
from portflow.streaming.consumer import ConsumeReport
from portflow.streaming.state import StreamStateStore


class FakeConsumer:
    def __init__(self) -> None:
        self.close_calls = 0

    def subscribe(self, _topics: Sequence[str]) -> None:
        pass

    def poll(self, _timeout: float) -> None:
        return None

    def commit(self, *, message: object, asynchronous: bool) -> None:
        del message, asynchronous

    def close(self) -> None:
        self.close_calls += 1


class FakeProducer:
    def produce(
        self,
        _topic: str,
        *,
        key: bytes,
        value: bytes,
        headers: Sequence[tuple[str, bytes]],
        callback: object,
    ) -> None:
        del key, value, headers, callback

    def poll(self, _timeout: float) -> int:
        return 0

    def flush(self, _timeout: float) -> int:
        return 0


def job_config(tmp_path: Path) -> StreamConsumerJobConfig:
    return StreamConsumerJobConfig(
        topic="portflow.telemetry",
        bronze_dir=tmp_path / "bronze",
        batch_size=2,
        max_messages=12,
        allowed_lateness_seconds=300,
        poll_timeout_seconds=1.0,
        idle_timeout_seconds=30.0,
    )


def streaming_config() -> StreamingConfig:
    return StreamingConfig(
        brokers="localhost:19092",
        topic="portflow.telemetry",
        group_id="portflow-bronze",
        batch_size=50,
        dlq_topic="portflow.telemetry.dlq",
        allowed_lateness_seconds=300,
    )


def fake_consumer_factory(_config: StreamingConfig) -> FakeConsumer:
    return FakeConsumer()


def fake_producer_factory(_config: StreamingConfig) -> FakeProducer:
    return FakeProducer()


def successful_report() -> ConsumeReport:
    return ConsumeReport(
        consumed_count=2,
        bronze_row_count=2,
        committed_count=1,
        batch_count=1,
        duplicate_count=0,
        late_count=0,
        dead_letter_count=0,
    )


def test_execute_stream_consumer_run_records_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_consume(consumer: object, **kwargs: object) -> ConsumeReport:
        del consumer
        captured.update(kwargs)
        return successful_report()

    monkeypatch.setattr(
        "portflow.orchestration.streaming.consume_telemetry_stream",
        fake_consume,
    )
    run_id = "dagster-success-1"

    result = execute_stream_consumer_run(
        run_id=run_id,
        job_config=job_config(tmp_path),
        env_config=streaming_config(),
        consumer_factory=fake_consumer_factory,
        producer_factory=fake_producer_factory,
    )

    assert result == successful_report()
    assert captured["run_id"] == run_id
    state_store = StreamStateStore(tmp_path / "bronze" / ".stream-state.sqlite3")
    saved = state_store.get_run(run_id)
    state_store.close()
    assert saved is not None
    assert saved.status == "succeeded"
    assert saved.committed_count == 1


def test_execute_stream_consumer_run_records_failure_and_reraises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_consume(consumer: object, **kwargs: object) -> ConsumeReport:
        del consumer, kwargs
        raise RuntimeError("consumer exploded")

    monkeypatch.setattr(
        "portflow.orchestration.streaming.consume_telemetry_stream",
        failing_consume,
    )
    run_id = "dagster-failure-1"

    with pytest.raises(RuntimeError, match="consumer exploded"):
        execute_stream_consumer_run(
            run_id=run_id,
            job_config=job_config(tmp_path),
            env_config=streaming_config(),
            consumer_factory=fake_consumer_factory,
            producer_factory=fake_producer_factory,
        )

    state_store = StreamStateStore(tmp_path / "bronze" / ".stream-state.sqlite3")
    saved = state_store.get_run(run_id)
    state_store.close()
    assert saved is not None
    assert saved.status == "failed"
    assert saved.error_type == "RuntimeError"
    assert saved.error_message == "consumer exploded"


def test_failure_metadata_error_does_not_replace_consumer_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_consume(consumer: object, **kwargs: object) -> ConsumeReport:
        del consumer, kwargs
        raise RuntimeError("consumer exploded")

    class FailingMetadataStore:
        def start_run(self, *, run_id: str, inputs: object) -> None:
            del run_id, inputs

        def record_run_failure(
            self,
            *,
            run_id: str,
            error_type: str,
            error_message: str,
            finished_at: object,
        ) -> None:
            del run_id, error_type, error_message, finished_at
            raise RuntimeError("metadata unavailable")

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        "portflow.orchestration.streaming.consume_telemetry_stream",
        failing_consume,
    )

    with pytest.raises(RuntimeError, match="consumer exploded"):
        execute_stream_consumer_run(
            run_id="dagster-metadata-failure-1",
            job_config=job_config(tmp_path),
            env_config=streaming_config(),
            consumer_factory=fake_consumer_factory,
            producer_factory=fake_producer_factory,
            state_store_factory=lambda _path: FailingMetadataStore(),
        )


def test_stream_consumer_job_passes_dagster_run_id_and_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_execute(
        *,
        run_id: str,
        job_config: StreamConsumerJobConfig,
        **_: object,
    ) -> ConsumeReport:
        captured["run_id"] = run_id
        captured["job_config"] = job_config
        return successful_report()

    monkeypatch.setattr(
        "portflow.orchestration.streaming.execute_stream_consumer_run",
        fake_execute,
    )
    result = stream_consumer_job.execute_in_process(
        run_config={
            "ops": {
                "consume_stream": {
                    "config": {
                        "topic": "portflow.telemetry",
                        "bronze_dir": str(tmp_path / "bronze"),
                        "batch_size": 2,
                        "max_messages": 2,
                        "allowed_lateness_seconds": 300,
                        "poll_timeout_seconds": 0.1,
                        "idle_timeout_seconds": 1.0,
                    }
                }
            }
        },
    )

    assert result.success
    assert isinstance(captured["run_id"], str)
    assert captured["run_id"]
    configured = captured["job_config"]
    assert isinstance(configured, StreamConsumerJobConfig)
    assert configured.topic == "portflow.telemetry"
    assert configured.bronze_dir == tmp_path / "bronze"
    assert configured.batch_size == 2
    assert configured.max_messages == 2
    assert configured.allowed_lateness_seconds == 300
    assert configured.poll_timeout_seconds == 0.1
    assert configured.idle_timeout_seconds == 1.0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("topic", "", "topic must not be empty"),
        ("max_messages", 0, "max_messages must be greater than zero"),
        ("allowed_lateness_seconds", -1, "allowed_lateness_seconds must not be negative"),
        ("poll_timeout_seconds", -0.1, "poll_timeout_seconds must not be negative"),
        ("idle_timeout_seconds", -0.1, "idle_timeout_seconds must not be negative"),
    ],
)
def test_execute_stream_consumer_run_rejects_invalid_job_config(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    config = job_config(tmp_path)
    invalid_config = replace(config, **{field: value})

    def unexpected_consumer_factory(_config: StreamingConfig) -> FakeConsumer:
        raise AssertionError("consumer factory must not be called")

    with pytest.raises(ValueError, match=message):
        execute_stream_consumer_run(
            run_id="invalid-config-1",
            job_config=invalid_config,
            env_config=streaming_config(),
            consumer_factory=unexpected_consumer_factory,
            producer_factory=fake_producer_factory,
        )
