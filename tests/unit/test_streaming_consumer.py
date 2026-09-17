import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

from portflow.domain.models import EquipmentState, TelemetryEvent
from portflow.ingestion.postgres_to_bronze import StreamBronzeWriteResult
from portflow.streaming.codec import (
    StreamValidationError,
    encode_telemetry_event,
    telemetry_headers,
)
from portflow.streaming.config import StreamingConfig
from portflow.streaming.consumer import (
    StreamConsumerError,
    consume_telemetry_stream,
    create_consumer,
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
class FakeMessage:
    payload: bytes | None
    message_headers: tuple[tuple[str, bytes | None], ...] | None
    message_offset: int = 0
    message_error: object | None = None

    def value(self) -> bytes | None:
        return self.payload

    def headers(self) -> tuple[tuple[str, bytes | None], ...] | None:
        return self.message_headers

    def offset(self) -> int:
        return self.message_offset

    def error(self) -> object | None:
        return self.message_error


def message_for(event: TelemetryEvent) -> FakeMessage:
    return FakeMessage(encode_telemetry_event(event), telemetry_headers())


class FakeConsumer:
    def __init__(self, messages: Sequence[FakeMessage]) -> None:
        self.messages = list(messages)
        self.subscribed: list[str] = []
        self.commits: list[tuple[FakeMessage, bool]] = []
        self.closed = False
        self.on_commit: Callable[[], None] | None = None

    def subscribe(self, topics: Sequence[str]) -> None:
        self.subscribed = list(topics)

    def poll(self, _timeout: float) -> FakeMessage | None:
        if not self.messages:
            return None
        return self.messages.pop(0)

    def commit(self, *, message: FakeMessage, asynchronous: bool) -> None:
        self.commits.append((message, asynchronous))
        if self.on_commit is not None:
            self.on_commit()

    def close(self) -> None:
        self.closed = True


def test_commits_only_after_writer_succeeds(tmp_path: Path) -> None:
    consumer = FakeConsumer([message_for(valid_event())])
    calls: list[str] = []

    def writer(
        events: Sequence[TelemetryEvent],
        *,
        bronze_dir: Path,
        run_id: str,
    ) -> StreamBronzeWriteResult:
        del bronze_dir, run_id
        calls.append("writer")
        return StreamBronzeWriteResult(
            "telemetry_events",
            len(events),
            tmp_path / "part.parquet",
            "hash",
        )

    consumer.on_commit = lambda: calls.append("commit")
    report = consume_telemetry_stream(
        consumer,
        topic="portflow.telemetry",
        bronze_dir=tmp_path,
        run_id="stream-run-000042",
        batch_size=1,
        max_messages=1,
        writer=writer,
    )

    assert report.consumed_count == 1
    assert report.bronze_row_count == 1
    assert report.committed_count == 1
    assert report.batch_count == 1
    assert calls == ["writer", "commit"]
    assert consumer.subscribed == ["portflow.telemetry"]
    assert len(consumer.commits) == 1
    assert consumer.commits[0][1] is False
    assert consumer.closed is True


def test_invalid_message_does_not_write_or_commit(tmp_path: Path) -> None:
    consumer = FakeConsumer(
        [FakeMessage(b'{"event_id":"bad"}', telemetry_headers())]
    )
    writer_calls: list[Sequence[TelemetryEvent]] = []

    def writer(
        events: Sequence[TelemetryEvent],
        *,
        bronze_dir: Path,
        run_id: str,
    ) -> StreamBronzeWriteResult:
        del bronze_dir, run_id
        writer_calls.append(events)
        raise AssertionError("invalid messages must not reach the writer")

    with pytest.raises(StreamValidationError, match="TelemetryEvent"):
        consume_telemetry_stream(
            consumer,
            topic="portflow.telemetry",
            bronze_dir=tmp_path,
            run_id="stream-run-000042",
            batch_size=1,
            max_messages=1,
            writer=writer,
        )

    assert writer_calls == []
    assert consumer.commits == []
    assert consumer.closed is True


def test_writer_failure_does_not_commit(tmp_path: Path) -> None:
    consumer = FakeConsumer([message_for(valid_event())])

    def writer(
        events: Sequence[TelemetryEvent],
        *,
        bronze_dir: Path,
        run_id: str,
    ) -> StreamBronzeWriteResult:
        del events, bronze_dir, run_id
        raise RuntimeError("writer failed")

    with pytest.raises(RuntimeError, match="writer failed"):
        consume_telemetry_stream(
            consumer,
            topic="portflow.telemetry",
            bronze_dir=tmp_path,
            run_id="stream-run-000042",
            batch_size=1,
            max_messages=1,
            writer=writer,
        )

    assert consumer.commits == []
    assert consumer.closed is True


def test_times_out_without_messages(tmp_path: Path) -> None:
    consumer = FakeConsumer([])

    with pytest.raises(StreamConsumerError, match="idle"):
        consume_telemetry_stream(
            consumer,
            topic="portflow.telemetry",
            bronze_dir=tmp_path,
            run_id="stream-run-000042",
            batch_size=1,
            max_messages=1,
            poll_timeout_seconds=0.0,
            idle_timeout_seconds=0.0,
        )

    assert consumer.commits == []
    assert consumer.closed is True


def test_consumer_closes_on_success_and_failure(tmp_path: Path) -> None:
    success_consumer = FakeConsumer([message_for(valid_event())])
    consume_telemetry_stream(
        success_consumer,
        topic="portflow.telemetry",
        bronze_dir=tmp_path,
        run_id="stream-run-000042",
        batch_size=1,
        max_messages=1,
    )

    failure_consumer = FakeConsumer(
        [FakeMessage(b"{}", (("portflow-event-type", b"wrong"),))]
    )
    with pytest.raises(StreamValidationError):
        consume_telemetry_stream(
            failure_consumer,
            topic="portflow.telemetry",
            bronze_dir=tmp_path,
            run_id="stream-run-000042",
            batch_size=1,
            max_messages=1,
        )

    assert success_consumer.closed is True
    assert failure_consumer.closed is True


def test_create_consumer_uses_edge_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, dict[str, str]] = {}

    class FakeKafkaConsumer:
        def __init__(self, properties: dict[str, str]) -> None:
            created["properties"] = properties

    kafka_module = ModuleType("confluent_kafka")
    kafka_module.Consumer = FakeKafkaConsumer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "confluent_kafka", kafka_module)

    config = StreamingConfig(
        brokers="redpanda:9092",
        topic="portflow.telemetry",
        group_id="portflow-bronze",
        batch_size=50,
    )

    consumer = create_consumer(config)

    assert isinstance(consumer, FakeKafkaConsumer)
    assert created["properties"] == {
        "bootstrap.servers": "redpanda:9092",
        "group.id": "portflow-bronze",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": "false",
    }
