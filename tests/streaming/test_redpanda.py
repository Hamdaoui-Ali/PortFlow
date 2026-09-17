import hashlib
import os
import uuid
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import polars as pl
import pytest

from portflow.ingestion.postgres_to_bronze import TABLE_SPECS, write_telemetry_bronze_batch
from portflow.seed import EQUIPMENT_ID, FIXTURE_START, TERMINAL_ID
from portflow.simulator.equipment import generate_telemetry
from portflow.streaming.config import StreamingConfig, consumer_properties
from portflow.streaming.consumer import ConsumeReport, consume_telemetry_stream, create_consumer
from portflow.streaming.producer import create_producer, publish_telemetry_events
from portflow.transforms.silver import transform_bronze_to_silver

pytestmark = [
    pytest.mark.redpanda,
    pytest.mark.skipif(
        not os.environ.get("PORTFLOW_REDPANDA_BROKERS"),
        reason="PORTFLOW_REDPANDA_BROKERS is not set",
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
