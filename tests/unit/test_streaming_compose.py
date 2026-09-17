import json
from pathlib import Path

import pytest
from scripts import run_stream_consumer, run_stream_producer

from portflow.domain.models import TelemetryEvent
from portflow.streaming.config import StreamingConfig
from portflow.streaming.consumer import ConsumeReport
from portflow.streaming.producer import PublishReport

REPOSITORY_ROOT = Path(__file__).parents[2]


def test_compose_keeps_redpanda_opt_in() -> None:
    compose = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "redpanda:" in compose
    assert "profiles:" in compose
    assert '"streaming"' in compose
    assert "docker.redpanda.com/redpandadata/redpanda:v26.2.2" in compose
    assert '"19092:19092"' in compose
    assert "--advertise-kafka-addr" in compose


def test_streaming_cleanup_is_scoped_to_redpanda() -> None:
    script = (REPOSITORY_ROOT / "scripts" / "verify_streaming.ps1").read_text(
        encoding="utf-8"
    )
    runbook = (REPOSITORY_ROOT / "docs" / "runbooks" / "local-streaming.md").read_text(
        encoding="utf-8"
    )
    cleanup = "docker compose --profile streaming down -v redpanda"

    assert cleanup in script
    assert cleanup in runbook


def test_producer_runner_forwards_seed_and_count(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}
    events = [object()]
    config = StreamingConfig("localhost:19092", "portflow.telemetry", "portflow-bronze", 50)
    producer = object()

    def fake_generate(
        *,
        seed: int,
        equipment_id: str,
        terminal_id: str,
        count: int,
        start_at: object,
    ) -> list[object]:
        captured["generate"] = (seed, equipment_id, terminal_id, count, start_at)
        return events

    def fake_config() -> StreamingConfig:
        return config

    def fake_create(received_config: StreamingConfig) -> object:
        captured["config"] = received_config
        return producer

    def fake_publish(
        received_events: list[TelemetryEvent] | list[object],
        *,
        producer: object,
        topic: str,
    ) -> PublishReport:
        captured["publish"] = (received_events, producer, topic)
        return PublishReport(topic=topic, published_count=len(received_events))

    monkeypatch.setattr(run_stream_producer, "generate_telemetry", fake_generate)
    monkeypatch.setattr(run_stream_producer.StreamingConfig, "from_env", fake_config)
    monkeypatch.setattr(run_stream_producer, "create_producer", fake_create)
    monkeypatch.setattr(run_stream_producer, "publish_telemetry_events", fake_publish)

    run_stream_producer.main(["--seed", "7", "--count", "3"])

    assert captured["generate"] == (
        7,
        run_stream_producer.EQUIPMENT_ID,
        run_stream_producer.TERMINAL_ID,
        3,
        run_stream_producer.FIXTURE_START,
    )
    assert captured["config"] == config
    assert captured["publish"] == (events, producer, "portflow.telemetry")
    assert json.loads(capsys.readouterr().out) == {
        "published_count": 1,
        "topic": "portflow.telemetry",
    }


def test_consumer_runner_forwards_max_messages_run_id_and_bronze_dir(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    config = StreamingConfig("localhost:19092", "portflow.telemetry", "portflow-bronze", 50)
    consumer = object()

    def fake_config() -> StreamingConfig:
        return config

    def fake_create(received_config: StreamingConfig) -> object:
        captured["config"] = received_config
        return consumer

    def fake_consume(
        received_consumer: object,
        *,
        topic: str,
        bronze_dir: Path,
        run_id: str,
        batch_size: int,
        max_messages: int,
    ) -> ConsumeReport:
        captured["consume"] = (
            received_consumer,
            topic,
            bronze_dir,
            run_id,
            batch_size,
            max_messages,
        )
        return ConsumeReport(7, 7, 2, 2)

    monkeypatch.setattr(run_stream_consumer.StreamingConfig, "from_env", fake_config)
    monkeypatch.setattr(run_stream_consumer, "create_consumer", fake_create)
    monkeypatch.setattr(run_stream_consumer, "consume_telemetry_stream", fake_consume)

    bronze_dir = tmp_path / "stream-bronze"
    run_stream_consumer.main(
        [
            "--max-messages",
            "7",
            "--run-id",
            "stream-run-000007",
            "--bronze-dir",
            str(bronze_dir),
        ]
    )

    assert captured["config"] == config
    assert captured["consume"] == (
        consumer,
        "portflow.telemetry",
        bronze_dir,
        "stream-run-000007",
        50,
        7,
    )
    assert json.loads(capsys.readouterr().out) == {
        "batch_count": 2,
        "bronze_row_count": 7,
        "committed_count": 2,
        "consumed_count": 7,
    }


def test_consumer_runner_requires_positive_max_messages() -> None:
    with pytest.raises(SystemExit):
        run_stream_consumer.main(["--max-messages", "0"])


def test_consumer_runner_uses_safe_default_for_empty_bronze_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    config = StreamingConfig("localhost:19092", "portflow.telemetry", "portflow-bronze", 50)

    def fake_config() -> StreamingConfig:
        return config

    def fake_create(received_config: StreamingConfig) -> object:
        assert received_config == config
        return object()

    def fake_consume(
        consumer: object,
        *,
        topic: str,
        bronze_dir: Path,
        run_id: str,
        batch_size: int,
        max_messages: int,
    ) -> ConsumeReport:
        del consumer, topic, run_id, batch_size, max_messages
        captured["bronze_dir"] = bronze_dir
        return ConsumeReport(1, 1, 1, 1)

    monkeypatch.setenv("PORTFLOW_STREAM_BRONZE_DIR", "")
    monkeypatch.setattr(run_stream_consumer.StreamingConfig, "from_env", fake_config)
    monkeypatch.setattr(run_stream_consumer, "create_consumer", fake_create)
    monkeypatch.setattr(run_stream_consumer, "consume_telemetry_stream", fake_consume)

    run_stream_consumer.main(["--max-messages", "1"])

    assert captured["bronze_dir"] == Path("data/bronze-stream")
