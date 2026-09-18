import base64
import hashlib
import json
import os
import time
import uuid
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import polars as pl
import pytest

from portflow.ingestion.postgres_to_bronze import TABLE_SPECS, write_telemetry_bronze_batch
from portflow.seed import EQUIPMENT_ID, FIXTURE_START, TERMINAL_ID
from portflow.simulator.equipment import generate_telemetry
from portflow.streaming.codec import encode_telemetry_event, telemetry_headers
from portflow.streaming.config import StreamingConfig, consumer_properties
from portflow.streaming.consumer import ConsumeReport, consume_telemetry_stream, create_consumer
from portflow.streaming.producer import create_producer, publish_telemetry_events
from portflow.transforms.silver import transform_bronze_to_silver

pytestmark = [
    pytest.mark.redpanda,
    pytest.mark.skipif(
        not os.environ.get("PORTFLOW_REDPANDA_BROKERS"),
        reason="PORTFLOW_REDPANDA_BROKERS is not set; start the streaming Compose profile",
    ),
]


def test_redpanda_round_trip(tmp_path: Path) -> None:
    from confluent_kafka import Consumer, TopicPartition
    from confluent_kafka.admin import AdminClient, NewTopic

    base_config = StreamingConfig.from_env()
    suffix = uuid.uuid4().hex[:12]
    topic = f"{base_config.topic}.test.{suffix}"
    group_id = f"{base_config.group_id}.test.{suffix}"
    config = replace(base_config, topic=topic, group_id=group_id)
    admin = AdminClient({"bootstrap.servers": config.brokers})
    topic_created = False

    try:
        create_future = admin.create_topics(
            [NewTopic(topic, num_partitions=1, replication_factor=1)]
        )[topic]
        create_future.result(timeout=30)
        topic_created = True

        events = generate_telemetry(
            seed=42,
            equipment_id=EQUIPMENT_ID,
            terminal_id=TERMINAL_ID,
            count=12,
            start_at=FIXTURE_START,
        )
        producer = create_producer(config)
        publish_report = publish_telemetry_events(events, producer=producer, topic=topic)

        bronze_dir = tmp_path / "bronze"
        consumer = create_consumer(config)
        consume_report = consume_telemetry_stream(
            consumer,
            topic=topic,
            bronze_dir=bronze_dir,
            run_id="stream-test-000042",
            batch_size=5,
            max_messages=12,
        )

        assert publish_report.published_count == 12
        assert consume_report == ConsumeReport(12, 12, 12, 3)

        actual_files = sorted((bronze_dir / "telemetry_events").rglob("*.parquet"))
        assert len(actual_files) == 3
        actual_frame = pl.concat([pl.read_parquet(path) for path in actual_files])
        assert actual_frame.columns == [
            *TABLE_SPECS["telemetry_events"].columns,
            "source_table",
            "extraction_run_id",
            "source_updated_at",
            "extracted_at",
        ]
        assert actual_frame.height == 12
        assert actual_frame["event_id"].to_list() == [event.event_id for event in events]

        expected_dir = tmp_path / "expected"
        expected_files = []
        for batch_start in (0, 5, 10):
            expected = write_telemetry_bronze_batch(
                events[batch_start : batch_start + 5],
                bronze_dir=expected_dir,
                run_id="stream-test-000042",
            )
            expected_files.append(expected.partition_path)

        for actual_path, expected_path in zip(actual_files, expected_files, strict=True):
            actual_bytes = actual_path.read_bytes()
            expected_bytes = expected_path.read_bytes()
            assert actual_bytes == expected_bytes
            actual_hash = hashlib.sha256(actual_bytes).hexdigest()
            expected_hash = hashlib.sha256(expected_bytes).hexdigest()
            assert actual_hash == expected_hash

        _write_reference_partitions(bronze_dir)
        silver_report = transform_bronze_to_silver(
            bronze_dir=bronze_dir,
            silver_dir=tmp_path / "silver",
            quarantine_dir=tmp_path / "quarantine",
        )
        assert silver_report.quarantine_rows == 0

        offset_consumer = Consumer(consumer_properties(config))
        try:
            committed = offset_consumer.committed([TopicPartition(topic, 0)], timeout=30)
            committed_offset = committed[0].offset
        finally:
            offset_consumer.close()
        assert committed_offset == 12
    finally:
        if topic_created:
            admin.delete_topics([topic])[topic].result(timeout=30)


def test_redpanda_stream_safety_round_trip(tmp_path: Path) -> None:
    from confluent_kafka import Consumer, TopicPartition
    from confluent_kafka.admin import AdminClient, NewTopic

    base_config = StreamingConfig.from_env()
    suffix = uuid.uuid4().hex[:12]
    topic = f"{base_config.topic}.safety.{suffix}"
    dlq_topic = f"{base_config.dlq_topic}.safety.{suffix}"
    group_id = f"{base_config.group_id}.safety.{suffix}"
    config = replace(
        base_config,
        topic=topic,
        dlq_topic=dlq_topic,
        group_id=group_id,
    )
    admin = AdminClient({"bootstrap.servers": config.brokers})
    topics_created = False

    try:
        futures = admin.create_topics(
            [
                NewTopic(topic, num_partitions=1, replication_factor=1),
                NewTopic(dlq_topic, num_partitions=1, replication_factor=1),
            ]
        )
        for future in futures.values():
            future.result(timeout=30)
        topics_created = True

        events = generate_telemetry(
            seed=42,
            equipment_id=EQUIPMENT_ID,
            terminal_id=TERMINAL_ID,
            count=2,
            start_at=FIXTURE_START,
        )
        late_event = events[1].model_copy(
            update={
                "event_id": "evt-000042-000003",
                "event_timestamp": FIXTURE_START - timedelta(minutes=10),
                "ingestion_timestamp": FIXTURE_START - timedelta(seconds=1),
            }
        )
        conflict = events[0].model_copy(
            update={"load_percent": events[0].load_percent + 1.0}
        )

        producer = create_producer(config)
        publish_telemetry_events(
            [events[0], events[0], events[1], late_event, conflict],
            producer=producer,
            topic=topic,
        )
        raw_errors: list[object] = []

        def on_raw_delivery(error: object | None, _message: object) -> None:
            if error is not None:
                raw_errors.append(error)

        producer.produce(
            topic,
            key=b"malformed-record",
            value=b"not-json",
            headers=list(telemetry_headers()),
            callback=on_raw_delivery,
        )
        producer.poll(0.0)
        assert producer.flush(30.0) == 0
        assert raw_errors == []

        bronze_dir = tmp_path / "bronze"
        first_consumer = create_consumer(config)
        first_report = consume_telemetry_stream(
            first_consumer,
            topic=topic,
            bronze_dir=bronze_dir,
            run_id="stream-test-safety-000042",
            batch_size=3,
            max_messages=6,
            dead_letter_producer=producer,
            dead_letter_topic=dlq_topic,
            allowed_lateness_seconds=300,
        )

        assert first_report == ConsumeReport(
            6,
            2,
            2,
            2,
            duplicate_count=1,
            late_count=1,
            dead_letter_count=3,
        )
        actual_files = sorted((bronze_dir / "telemetry_events").rglob("*.parquet"))
        assert len(actual_files) == 1
        actual_frame = pl.concat([pl.read_parquet(path) for path in actual_files])
        assert actual_frame.height == 2
        assert actual_frame["event_id"].to_list() == [event.event_id for event in events]

        dlq_messages = _read_topic_messages(
            config,
            dlq_topic,
            expected_count=3,
        )
        dlq_envelopes = [json.loads(message.value()) for message in dlq_messages]
        assert [envelope["reason_code"] for envelope in dlq_envelopes] == [
            "late_event",
            "duplicate_conflict",
            "invalid_telemetry",
        ]
        assert all(envelope["source_topic"] == topic for envelope in dlq_envelopes)
        assert dlq_envelopes[0]["source_value_base64"] == base64.b64encode(
            encode_telemetry_event(late_event)
        ).decode("ascii")
        assert dlq_envelopes[2]["source_value_base64"] == base64.b64encode(
            b"not-json"
        ).decode("ascii")
        assert dict(dlq_messages[0].headers()) == {
            "portflow-dead-letter-reason": b"late_event",
            "portflow-schema-version": b"1",
        }

        second_config = replace(
            config,
            group_id=f"{group_id}.replay",
        )
        second_consumer = create_consumer(second_config)
        second_report = consume_telemetry_stream(
            second_consumer,
            topic=topic,
            bronze_dir=bronze_dir,
            run_id="stream-test-safety-replay",
            batch_size=6,
            max_messages=6,
            dead_letter_producer=producer,
            dead_letter_topic=dlq_topic,
            allowed_lateness_seconds=300,
        )

        assert second_report.consumed_count == 6
        assert second_report.bronze_row_count == 0
        assert second_report.duplicate_count == 4
        assert second_report.dead_letter_count == 2
        assert len(sorted((bronze_dir / "telemetry_events").rglob("*.parquet"))) == 1

        offset_consumer = Consumer(consumer_properties(config))
        try:
            committed = offset_consumer.committed([TopicPartition(topic, 0)], timeout=30)
            committed_offset = committed[0].offset
        finally:
            offset_consumer.close()
        assert committed_offset == 6
    finally:
        if topics_created:
            delete_futures = admin.delete_topics([topic, dlq_topic])
            for delete_future in delete_futures.values():
                delete_future.result(timeout=30)


def _read_topic_messages(
    config: StreamingConfig,
    topic: str,
    *,
    expected_count: int,
) -> list[object]:
    from confluent_kafka import Consumer

    reader_config = replace(config, group_id=f"{config.group_id}.dlq-reader.{uuid.uuid4().hex[:8]}")
    reader = Consumer(consumer_properties(reader_config))
    reader.subscribe([topic])
    messages: list[object] = []
    deadline = time.monotonic() + 30.0
    try:
        while len(messages) < expected_count:
            if time.monotonic() >= deadline:
                raise AssertionError(f"timed out reading {expected_count} records from {topic}")
            message = reader.poll(1.0)
            if message is None:
                continue
            if message.error() is not None:
                raise AssertionError(f"DLQ read failed: {message.error()}")
            messages.append(message)
    finally:
        reader.close()
    return messages


def _write_reference_partitions(bronze_dir: Path) -> None:
    metadata = {
        "source_table": "",
        "extraction_run_id": "stream-test-reference",
        "source_updated_at": FIXTURE_START,
        "extracted_at": FIXTURE_START + timedelta(seconds=2),
    }
    references = {
        "terminals": {
            "terminal_id": TERMINAL_ID,
            "name": "PortFlow Demo Terminal",
            "timezone_name": "UTC",
            "created_at": FIXTURE_START,
            "updated_at": FIXTURE_START,
        },
        "equipment": {
            "equipment_id": EQUIPMENT_ID,
            "terminal_id": TERMINAL_ID,
            "equipment_type": "QUAY_CRANE",
            "commissioning_date": date(2024, 1, 1),
            "created_at": FIXTURE_START,
            "updated_at": FIXTURE_START,
        },
    }
    for table_name, source_row in references.items():
        row = {
            **source_row,
            **metadata,
            "source_table": table_name,
        }
        columns = [
            *TABLE_SPECS[table_name].columns,
            "source_table",
            "extraction_run_id",
            "source_updated_at",
            "extracted_at",
        ]
        path = bronze_dir / table_name / "date=2026-09-02" / "part-reference.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame([row]).select(columns).write_parquet(path, compression="zstd")
