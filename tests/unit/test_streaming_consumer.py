import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest

from portflow.domain.models import EquipmentState, TelemetryEvent
from portflow.ingestion.postgres_to_bronze import StreamBronzeWriteResult
from portflow.streaming.codec import (
    encode_telemetry_event,
    telemetry_headers,
    telemetry_payload_sha256,
)
from portflow.streaming.config import StreamingConfig
from portflow.streaming.consumer import (
    StreamConsumerError,
    consume_telemetry_stream,
    create_consumer,
)
from portflow.streaming.producer import ProducerDeliveryError
from portflow.streaming.state import StreamStateError, StreamStateStore


def valid_event(
    event_id: str = "evt-000042-000001",
    minute: int = 0,
) -> TelemetryEvent:
    timestamp = datetime(2026, 9, 2, 0, minute, tzinfo=UTC)
    return TelemetryEvent(
        event_id=event_id,
        schema_version=1,
        equipment_id="QC-001",
        terminal_id="TM-001",
        event_timestamp=timestamp,
        ingestion_timestamp=timestamp.replace(second=2),
        state=EquipmentState.ACTIVE,
        available=True,
        load_percent=50.0 + minute,
        temperature_c=55.0,
    )


@dataclass(frozen=True, slots=True)
class FakeMessage:
    payload: bytes | None
    message_headers: tuple[tuple[str, bytes | None], ...] | None
    message_offset: int = 0
    message_key: bytes | None = b"evt-000042-000001"
    message_partition: int = 0
    message_error: object | None = None

    def value(self) -> bytes | None:
        return self.payload

    def headers(self) -> tuple[tuple[str, bytes | None], ...] | None:
        return self.message_headers

    def offset(self) -> int:
        return self.message_offset

    def key(self) -> bytes | None:
        return self.message_key

    def partition(self) -> int:
        return self.message_partition

    def error(self) -> object | None:
        return self.message_error


def message_for(
    event: TelemetryEvent,
    *,
    offset: int = 0,
    key: bytes | None = None,
) -> FakeMessage:
    return FakeMessage(
        encode_telemetry_event(event),
        telemetry_headers(),
        message_offset=offset,
        message_key=event.event_id.encode() if key is None else key,
    )


@dataclass(frozen=True, slots=True)
class ProduceCall:
    topic: str
    key: bytes
    value: bytes
    headers: list[tuple[str, bytes]]


class FakeProducer:
    def __init__(
        self,
        delivery_error: object | None = None,
        remaining: int = 0,
    ) -> None:
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


def test_invalid_message_requires_dlq_dependencies_before_mutation(tmp_path: Path) -> None:
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

    with pytest.raises(StreamConsumerError, match="dead-letter"):
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


def test_rejects_whitespace_run_id_before_consuming(tmp_path: Path) -> None:
    consumer = FakeConsumer([message_for(valid_event())])

    with pytest.raises(ValueError, match="run_id"):
        consume_telemetry_stream(
            consumer,
            topic="portflow.telemetry",
            bronze_dir=tmp_path,
            run_id="   ",
            batch_size=1,
            max_messages=1,
        )

    assert consumer.subscribed == []
    assert consumer.commits == []
    assert not list(tmp_path.rglob("*.parquet"))


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
    with pytest.raises(StreamConsumerError, match="dead-letter"):
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


def result_for(row_count: int, tmp_path: Path) -> StreamBronzeWriteResult:
    return StreamBronzeWriteResult(
        "telemetry_events",
        row_count,
        tmp_path / "part.parquet",
        "hash",
    )


def test_exact_duplicate_is_not_written_twice(tmp_path: Path) -> None:
    event = valid_event()
    consumer = FakeConsumer([message_for(event), message_for(event, offset=1)])
    writer_calls: list[Sequence[TelemetryEvent]] = []
    state_store = StreamStateStore(tmp_path / "state.sqlite3")

    def writer(
        events: Sequence[TelemetryEvent],
        *,
        bronze_dir: Path,
        run_id: str,
    ) -> StreamBronzeWriteResult:
        del bronze_dir, run_id
        writer_calls.append(events)
        return result_for(len(events), tmp_path)

    report = consume_telemetry_stream(
        consumer,
        topic="portflow.telemetry",
        bronze_dir=tmp_path,
        run_id="stream-run-000042",
        batch_size=1,
        max_messages=2,
        writer=writer,
        state_store=state_store,
    )

    assert report.consumed_count == 2
    assert report.bronze_row_count == 1
    assert report.duplicate_count == 1
    assert report.late_count == 0
    assert report.dead_letter_count == 0
    assert len(writer_calls) == 1
    assert len(consumer.commits) == 2
    state_store.close()


def test_duplicate_conflict_is_dead_lettered_without_overwriting_state(
    tmp_path: Path,
) -> None:
    original = valid_event()
    conflict = original.model_copy(update={"load_percent": 75.0})
    consumer = FakeConsumer([message_for(original), message_for(conflict, offset=1)])
    producer = FakeProducer()
    state_store = StreamStateStore(tmp_path / "state.sqlite3")
    writer_calls: list[Sequence[TelemetryEvent]] = []

    def writer(
        events: Sequence[TelemetryEvent],
        *,
        bronze_dir: Path,
        run_id: str,
    ) -> StreamBronzeWriteResult:
        del bronze_dir, run_id
        writer_calls.append(events)
        return result_for(len(events), tmp_path)

    report = consume_telemetry_stream(
        consumer,
        topic="portflow.telemetry",
        bronze_dir=tmp_path,
        run_id="stream-run-000042",
        batch_size=2,
        max_messages=2,
        writer=writer,
        dead_letter_producer=producer,
        dead_letter_topic="portflow.telemetry.dlq",
        state_store=state_store,
    )

    saved = state_store.get_event(original.event_id)
    assert saved is not None
    assert saved.outcome == "bronze"
    assert saved.payload_sha256 == telemetry_payload_sha256(original)
    assert saved.payload_sha256 != telemetry_payload_sha256(conflict)
    assert len(writer_calls) == 1
    assert report.bronze_row_count == 1
    assert report.duplicate_count == 0
    assert report.dead_letter_count == 1
    assert json.loads(producer.calls[0].value)["reason_code"] == "duplicate_conflict"
    assert len(consumer.commits) == 1
    state_store.close()


def test_lateness_boundary_is_accepted_and_one_microsecond_beyond_is_dead_lettered(
    tmp_path: Path,
) -> None:
    watermark_event = valid_event("evt-000042-000010", minute=10)
    boundary = valid_event("evt-000042-000011", minute=5)
    late_base = valid_event("evt-000042-000012", minute=5)
    just_late = late_base.model_copy(
        update={
            "ingestion_timestamp": late_base.ingestion_timestamp - timedelta(microseconds=1)
        }
    )
    state_store = StreamStateStore(tmp_path / "state.sqlite3")
    state_store.record_bronze(topic="portflow.telemetry", events=[watermark_event])
    producer = FakeProducer()
    consumer = FakeConsumer([message_for(boundary), message_for(just_late, offset=1)])
    writer_calls: list[Sequence[TelemetryEvent]] = []

    def writer(
        events: Sequence[TelemetryEvent],
        *,
        bronze_dir: Path,
        run_id: str,
    ) -> StreamBronzeWriteResult:
        del bronze_dir, run_id
        writer_calls.append(events)
        return result_for(len(events), tmp_path)

    report = consume_telemetry_stream(
        consumer,
        topic="portflow.telemetry",
        bronze_dir=tmp_path,
        run_id="stream-run-000042",
        batch_size=2,
        max_messages=2,
        writer=writer,
        dead_letter_producer=producer,
        dead_letter_topic="portflow.telemetry.dlq",
        allowed_lateness_seconds=300,
        state_store=state_store,
    )

    assert report.bronze_row_count == 1
    assert report.late_count == 1
    assert report.dead_letter_count == 1
    assert [event.event_id for event in writer_calls[0]] == [boundary.event_id]
    assert state_store.get_event(boundary.event_id) is not None
    assert state_store.get_event(just_late.event_id).outcome == "dead_letter"  # type: ignore[union-attr]
    state_store.close()


def test_malformed_message_is_dead_lettered_before_commit(tmp_path: Path) -> None:
    consumer = FakeConsumer([FakeMessage(b"\xff", telemetry_headers())])
    producer = FakeProducer()
    state_store = StreamStateStore(tmp_path / "state.sqlite3")
    writer_calls: list[Sequence[TelemetryEvent]] = []

    def writer(
        events: Sequence[TelemetryEvent],
        *,
        bronze_dir: Path,
        run_id: str,
    ) -> StreamBronzeWriteResult:
        del events, bronze_dir, run_id
        writer_calls.append([])
        raise AssertionError("malformed messages must not reach the writer")

    report = consume_telemetry_stream(
        consumer,
        topic="portflow.telemetry",
        bronze_dir=tmp_path,
        run_id="stream-run-000042",
        batch_size=1,
        max_messages=1,
        writer=writer,
        dead_letter_producer=producer,
        dead_letter_topic="portflow.telemetry.dlq",
        state_store=state_store,
    )

    envelope = json.loads(producer.calls[0].value)
    assert report.dead_letter_count == 1
    assert report.committed_count == 1
    assert envelope["reason_code"] == "invalid_telemetry"
    assert envelope["source_value_base64"] == "/w=="
    assert writer_calls == []
    assert len(consumer.commits) == 1
    state_store.close()


def test_batch_containing_only_duplicates_skips_writer(tmp_path: Path) -> None:
    event = valid_event()
    state_store = StreamStateStore(tmp_path / "state.sqlite3")
    state_store.record_bronze(topic="portflow.telemetry", events=[event])
    consumer = FakeConsumer([message_for(event)])

    def writer(
        events: Sequence[TelemetryEvent],
        *,
        bronze_dir: Path,
        run_id: str,
    ) -> StreamBronzeWriteResult:
        del events, bronze_dir, run_id
        raise AssertionError("duplicate-only batches must skip the writer")

    report = consume_telemetry_stream(
        consumer,
        topic="portflow.telemetry",
        bronze_dir=tmp_path,
        run_id="stream-run-000042",
        batch_size=1,
        max_messages=1,
        writer=writer,
        state_store=state_store,
    )

    assert report.bronze_row_count == 0
    assert report.duplicate_count == 1
    assert report.committed_count == 1
    state_store.close()


def test_reopened_state_store_suppresses_prior_event(tmp_path: Path) -> None:
    event = valid_event()
    state_path = tmp_path / "state.sqlite3"
    first_store = StreamStateStore(state_path)
    first_consumer = FakeConsumer([message_for(event)])

    consume_telemetry_stream(
        first_consumer,
        topic="portflow.telemetry",
        bronze_dir=tmp_path,
        run_id="stream-run-000042",
        batch_size=1,
        max_messages=1,
        state_store=first_store,
    )
    first_store.close()

    second_store = StreamStateStore(state_path)
    second_consumer = FakeConsumer([message_for(event)])
    report = consume_telemetry_stream(
        second_consumer,
        topic="portflow.telemetry",
        bronze_dir=tmp_path,
        run_id="stream-run-000043",
        batch_size=1,
        max_messages=1,
        writer=lambda *_events, **_kwargs: (_ for _ in ()).throw(
            AssertionError("replayed event must not reach writer")
        ),
        state_store=second_store,
    )

    assert report.duplicate_count == 1
    assert report.bronze_row_count == 0
    second_store.close()


def test_report_counts_source_outcomes_and_commits(tmp_path: Path) -> None:
    original = valid_event("evt-000042-000020", minute=10)
    later = valid_event("evt-000042-000021", minute=11)
    late = valid_event("evt-000042-000022", minute=4)
    state_store = StreamStateStore(tmp_path / "state.sqlite3")
    state_store.record_bronze(topic="portflow.telemetry", events=[original])
    producer = FakeProducer()
    consumer = FakeConsumer(
        [
            message_for(original),
            message_for(later, offset=1),
            message_for(late, offset=2),
            FakeMessage(b"not-json", telemetry_headers(), message_offset=3),
        ]
    )

    report = consume_telemetry_stream(
        consumer,
        topic="portflow.telemetry",
        bronze_dir=tmp_path,
        run_id="stream-run-000042",
        batch_size=4,
        max_messages=4,
        dead_letter_producer=producer,
        dead_letter_topic="portflow.telemetry.dlq",
        state_store=state_store,
    )

    assert report == type(report)(
        consumed_count=4,
        bronze_row_count=1,
        committed_count=1,
        batch_count=1,
        duplicate_count=1,
        late_count=1,
        dead_letter_count=2,
    )
    assert len(producer.calls) == 2
    state_store.close()


def test_state_failure_does_not_commit(tmp_path: Path) -> None:
    class FailingStateStore:
        def get_watermark(self, _topic: str) -> None:
            return None

        def get_event(self, _event_id: str) -> None:
            return None

        def record_bronze(
            self,
            *,
            topic: str,
            events: Sequence[TelemetryEvent],
        ) -> None:
            del topic, events
            raise StreamStateError("state failed")

        def record_dead_letter(
            self,
            *,
            topic: str,
            event: TelemetryEvent,
            reason_code: str,
        ) -> None:
            del topic, event, reason_code

        def close(self) -> None:
            pass

    consumer = FakeConsumer([message_for(valid_event())])

    with pytest.raises(StreamStateError, match="state failed"):
        consume_telemetry_stream(
            consumer,
            topic="portflow.telemetry",
            bronze_dir=tmp_path,
            run_id="stream-run-000042",
            batch_size=1,
            max_messages=1,
            state_store=FailingStateStore(),  # type: ignore[arg-type]
        )

    assert consumer.commits == []


def test_dlq_failure_does_not_commit(tmp_path: Path) -> None:
    consumer = FakeConsumer([FakeMessage(b"not-json", telemetry_headers())])

    with pytest.raises(ProducerDeliveryError, match="broker rejected"):
        consume_telemetry_stream(
            consumer,
            topic="portflow.telemetry",
            bronze_dir=tmp_path,
            run_id="stream-run-000042",
            batch_size=1,
            max_messages=1,
            dead_letter_producer=FakeProducer(delivery_error="broker rejected"),
            dead_letter_topic="portflow.telemetry.dlq",
        )

    assert consumer.commits == []


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
        dlq_topic="portflow.telemetry.dlq",
        allowed_lateness_seconds=300,
    )

    consumer = create_consumer(config)

    assert isinstance(consumer, FakeKafkaConsumer)
    assert created["properties"] == {
        "bootstrap.servers": "redpanda:9092",
        "group.id": "portflow-bronze",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": "false",
    }
