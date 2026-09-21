# PF-101 Redpanda Local Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in local Redpanda telemetry path that publishes the existing TelemetryEvent contract and consumes it into the existing Bronze Parquet contract without changing PortFlow's public static product.

**Architecture:** Add a single-node Redpanda Docker Compose service behind a streaming profile. Use a small confluent-kafka edge adapter, canonical JSON telemetry messages keyed by event ID, manual consumer offset commits, and a transport-neutral writer that reuses the existing telemetry Bronze schema and atomic partition behavior. Keep deduplication, late-event handling, DLQ routing, and all public/UI behavior outside this slice.

**Tech Stack:** Python 3.12, Pydantic 2, Polars, existing Bronze Parquet writer, confluent-kafka, Redpanda Community-compatible Docker image, Docker Compose, pytest, mypy, Ruff, GitHub Actions.

**Spec:** docs/superpowers/specs/2026-09-17-portflow-pf-101-redpanda-streaming-design.md

## Global Constraints

- Keep the public PortFlow application static and snapshot-driven; the browser never connects to Redpanda, Kafka, PostgreSQL, Parquet, or the local consumer.
- Keep PF-101 telemetry-only on portflow.telemetry; alarm, incident, movement, weather, and other topics are not part of this plan.
- Use the existing TelemetryEvent model and the existing TABLE_SPECS telemetry_events column order; do not introduce a second telemetry payload schema.
- Use canonical UTF-8 JSON with sorted keys and compact separators; message keys are UTF-8 event IDs.
- Disable automatic consumer offset commits and commit synchronously only after Bronze publication succeeds.
- Preserve at-least-once behavior; duplicate suppression, late events, and DLQ routing belong to PF-102.
- Add Redpanda only behind the streaming Compose profile; docker compose up -d --wait postgres and scripts/verify_r2.ps1 remain broker-free.
- Keep confluent-kafka types behind src/portflow/streaming edge factories and use protocols/fakes in unit tests.
- Do not add Redpanda Console, Schema Registry, Avro, Protobuf, transactions, exactly-once processing, multi-broker deployment, public writes, cloud credentials, or a continuously running service.
- Keep the approved PortFlow UI system and five navigation destinations unchanged.
- Tests must be written first and observed failing for the intended reason; each task ends with a focused test run and an independent commit.

## File Map

| File | Responsibility |
| --- | --- |
| pyproject.toml | Add the locked confluent-kafka dependency and the redpanda pytest marker. |
| uv.lock | Lock the new Python dependency and transitive packages. |
| .env.example | Document local Redpanda brokers, topic, group, batch size, and stream Bronze directory. |
| src/portflow/streaming/__init__.py | Keep the streaming package importable and expose only stable public symbols. |
| src/portflow/streaming/config.py | Parse validated environment configuration and build edge client properties. |
| src/portflow/streaming/codec.py | Serialize, validate headers for, and decode telemetry messages. |
| src/portflow/streaming/producer.py | Publish validated telemetry through a narrow producer protocol. |
| src/portflow/streaming/consumer.py | Poll, validate, write Bronze batches, and commit offsets after publication. |
| src/portflow/ingestion/postgres_to_bronze.py | Add the public telemetry stream-to-Bronze adapter while preserving PostgreSQL extraction behavior. |
| tests/unit/test_streaming_config.py | Configuration defaults and rejection tests. |
| tests/unit/test_streaming_codec.py | Canonical JSON, header, round-trip, and validation tests. |
| tests/unit/test_streaming_bronze.py | Stream row mapping, metadata, deterministic ordering, and atomic writer tests. |
| tests/unit/test_streaming_producer.py | Producer protocol, event key, headers, delivery, and failure tests. |
| tests/unit/test_streaming_consumer.py | Consumer batching, writer/commit ordering, timeout, invalid message, and close tests. |
| tests/unit/test_streaming_compose.py | Compose profile and CLI contract tests. |
| tests/streaming/test_redpanda.py | Opt-in real broker round-trip and Silver compatibility test. |
| compose.yaml | Add one opt-in Redpanda service with a host Kafka listener on port 19092. |
| scripts/run_stream_producer.py | Publish a deterministic simulator fixture to the configured topic. |
| scripts/run_stream_consumer.py | Consume a bounded number of messages into a configured Bronze directory. |
| scripts/verify_streaming.ps1 | Start the Compose profile, run the focused Redpanda test, and remove the disposable broker. |
| .github/workflows/streaming.yml | Run the real Redpanda round-trip as a separate CI check without changing the V1 gate. |
| docs/runbooks/local-streaming.md | Document setup, producer, consumer, verification, cleanup, and failure behavior. |
| README.md | Link the streaming runbook and keep the public/static boundary explicit. |
| docs/product/BACKLOG.md | Record PF-101 completion and point the next post-V1 slice at PF-102 while preserving the branch-protection note. |
| CHANGELOG.md | Record the post-V1 local streaming slice and its explicit exclusions. |

---

### Task 1: Add the streaming dependency and configuration contract

**Files:**
- Modify: pyproject.toml
- Modify: uv.lock
- Modify: .env.example
- Create: src/portflow/streaming/__init__.py
- Create: src/portflow/streaming/config.py
- Create: tests/unit/test_streaming_config.py

**Interfaces:**

~~~python
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
        pass

def producer_properties(config: StreamingConfig) -> dict[str, str]:
    pass

def consumer_properties(config: StreamingConfig) -> dict[str, str]:
    pass
~~~

Use defaults localhost:19092, portflow.telemetry, portflow-bronze, and 50 for PORTFLOW_REDPANDA_BROKERS, PORTFLOW_REDPANDA_TOPIC, PORTFLOW_REDPANDA_GROUP, and PORTFLOW_STREAM_BATCH_SIZE. Add PORTFLOW_STREAM_BRONZE_DIR=data/bronze-stream for the CLI default.

- [ ] **Step 1: Write failing configuration tests.**

~~~python
def test_defaults_are_safe_for_local_compose() -> None:
    config = StreamingConfig.from_env({})

    assert config == StreamingConfig(
        brokers="localhost:19092",
        topic="portflow.telemetry",
        group_id="portflow-bronze",
        batch_size=50,
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
        {"PORTFLOW_STREAM_BATCH_SIZE": "0"},
        {"PORTFLOW_STREAM_BATCH_SIZE": "not-an-int"},
    ],
)
def test_rejects_invalid_values(env: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        StreamingConfig.from_env(env)
~~~

- [ ] **Step 2: Run the focused tests before implementation.**

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_config.py -q
~~~

Expected: FAIL because portflow.streaming does not exist.

- [ ] **Step 3: Add and lock confluent-kafka.**

Add this dependency in pyproject.toml:

~~~toml
"confluent-kafka>=2.12,<3",
~~~

Run python -m uv lock and confirm uv.lock contains the resolved package. Do not add a second Kafka client.

- [ ] **Step 4: Implement StreamingConfig and edge properties.**

Read from the supplied mapping or os.environ, trim string values, parse the batch size with int, and raise ValueError for an empty broker/topic/group, a non-integer batch size, or a batch size less than one. Return exactly the property dictionaries asserted above; the consumer property enable.auto.commit must remain the string false.

- [ ] **Step 5: Run tests, lint, and commit.**

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_config.py -q
./.venv/Scripts/python.exe -m ruff check src/portflow/streaming tests/unit/test_streaming_config.py
python -m uv lock --check
git add pyproject.toml uv.lock .env.example src/portflow/streaming tests/unit/test_streaming_config.py
git commit -m "build: configure local streaming client"
~~~

Expected: all configuration tests pass, Ruff passes, and the lockfile is consistent.

---

### Task 2: Implement the telemetry message codec

**Files:**
- Create: src/portflow/streaming/codec.py
- Create: tests/unit/test_streaming_codec.py

**Interfaces:**

~~~python
from collections.abc import Sequence
from typing import TypeAlias

Header: TypeAlias = tuple[str, bytes | None]

class StreamValidationError(ValueError):
    """Raised when a stream record is not a valid PortFlow telemetry message."""

def telemetry_headers() -> tuple[tuple[str, bytes], ...]:
    pass

def encode_telemetry_event(event: TelemetryEvent) -> bytes:
    pass

def decode_telemetry_event(
    payload: bytes | None,
    headers: Sequence[Header] | None,
) -> TelemetryEvent:
    pass
~~~

telemetry_headers returns exactly (("portflow-event-type", b"telemetry"), ("portflow-schema-version", b"1")). Encode with event.model_dump(mode="json") followed by json.dumps with sort_keys=True, separators=(",", ":"), ensure_ascii=False, and UTF-8 encoding. Decode must reject None, invalid UTF-8, non-object JSON, missing/wrong/duplicate headers, and Pydantic validation errors by raising StreamValidationError.

- [ ] **Step 1: Write failing codec tests.**

~~~python
def test_encoding_is_canonical_and_round_trips() -> None:
    event = valid_event()

    encoded = encode_telemetry_event(event)

    assert encoded == encode_telemetry_event(event)
    assert decode_telemetry_event(encoded, telemetry_headers()) == event
    assert list(json.loads(encoded)) == sorted(json.loads(encoded))


def test_decoder_rejects_bad_payload_and_headers() -> None:
    with pytest.raises(StreamValidationError, match="headers"):
        decode_telemetry_event(b"{}", (("portflow-event-type", b"wrong"),))

    with pytest.raises(StreamValidationError, match="UTF-8"):
        decode_telemetry_event(b"\xff", telemetry_headers())

    with pytest.raises(StreamValidationError, match="TelemetryEvent"):
        decode_telemetry_event(b'{"event_id":"bad"}', telemetry_headers())
~~~

- [ ] **Step 2: Run codec tests before implementation.**

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_codec.py -q
~~~

Expected: FAIL because codec.py does not exist.

- [ ] **Step 3: Implement canonical encoding and header validation.**

Build the value only from the frozen domain model. Normalize UnicodeDecodeError, JSONDecodeError, non-dict JSON values, and pydantic.ValidationError into StreamValidationError. Check header names and values before decoding the payload; do not accept missing headers or duplicate header values.

- [ ] **Step 4: Run codec tests and commit.**

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_codec.py -q
./.venv/Scripts/python.exe -m ruff check src/portflow/streaming/codec.py tests/unit/test_streaming_codec.py
git add src/portflow/streaming/codec.py tests/unit/test_streaming_codec.py
git commit -m "feat: add telemetry stream codec"
~~~

Expected: canonical serialization, header checks, invalid-payload handling, and Ruff all pass.

---

### Task 3: Add the transport-neutral stream-to-Bronze writer

**Files:**
- Modify: src/portflow/ingestion/postgres_to_bronze.py
- Create: tests/unit/test_streaming_bronze.py

**Interfaces:**

Add these public types/functions without changing extract_table or its existing return type:

~~~python
from collections.abc import Sequence

@dataclass(frozen=True, slots=True)
class StreamBronzeWriteResult:
    table_name: str
    row_count: int
    partition_path: Path
    content_sha256: str

def write_telemetry_bronze_batch(
    events: Sequence[TelemetryEvent],
    *,
    bronze_dir: Path,
    run_id: str,
) -> StreamBronzeWriteResult:
    pass
~~~

Use TABLE_SPECS["telemetry_events"], the existing private atomic _write_batch helper, and a SourceCursor built from the greatest (event.ingestion_timestamp, event.event_id) after sorting. Map each event to this exact source-column tuple:

~~~python
(
    event.event_id,
    event.schema_version,
    event.equipment_id,
    event.terminal_id,
    event.event_timestamp,
    event.ingestion_timestamp,
    event.state.value,
    event.available,
    event.load_percent,
    event.temperature_c,
    event.ingestion_timestamp,
    event.ingestion_timestamp,
)
~~~

The existing writer then adds source_table, extraction_run_id, source_updated_at, and deterministic extracted_at metadata. Reject an empty event sequence or empty run ID before creating directories.

- [ ] **Step 1: Write failing Bronze writer tests.**

Create two valid TelemetryEvent values with distinct five-minute timestamps. Test the column contract and metadata:

~~~python
def test_stream_batch_matches_existing_telemetry_bronze_contract(tmp_path: Path) -> None:
    events = [event("evt-000042-000001", 0), event("evt-000042-000002", 5)]

    result = write_telemetry_bronze_batch(
        list(reversed(events)),
        bronze_dir=tmp_path / "bronze",
        run_id="stream-run-000042",
    )
    frame = pl.read_parquet(result.partition_path)

    assert result.table_name == "telemetry_events"
    assert result.row_count == 2
    assert frame.columns == [
        *TABLE_SPECS["telemetry_events"].columns,
        "source_table",
        "extraction_run_id",
        "source_updated_at",
        "extracted_at",
    ]
    assert frame["event_id"].to_list() == [
        "evt-000042-000001",
        "evt-000042-000002",
    ]
    assert frame["source_table"].unique().to_list() == ["telemetry_events"]
    assert frame["extraction_run_id"].unique().to_list() == ["stream-run-000042"]
~~~

Also add test_reversed_input_reuses_the_same_partition_hash and test_rejects_empty_events_and_run_id. The first writes the same events in both orders and asserts equal content_sha256 and bytes; the second asserts ValueError and no Parquet output.

- [ ] **Step 2: Run the Bronze tests before implementation.**

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_bronze.py -q
~~~

Expected: FAIL because write_telemetry_bronze_batch does not exist.

- [ ] **Step 3: Implement the adapter by reusing the existing writer.**

Import TelemetryEvent, SourceCursor, and Sequence. Sort a copy of the input by (ingestion_timestamp, event_id), build the tuples above, create the final cursor from the sorted final event, and call _write_batch with the existing telemetry TableSpec. Return the target path and content hash in StreamBronzeWriteResult. Do not duplicate Parquet staging, hashing, or atomic rename logic.

- [ ] **Step 4: Run regression and focused tests, then commit.**

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_bronze.py tests/unit/test_cursor.py tests/unit/test_telemetry_contract.py -q
./.venv/Scripts/python.exe -m ruff check src/portflow/ingestion/postgres_to_bronze.py tests/unit/test_streaming_bronze.py
./.venv/Scripts/python.exe -m mypy src/portflow/ingestion
git add src/portflow/ingestion/postgres_to_bronze.py tests/unit/test_streaming_bronze.py
git commit -m "feat: write stream telemetry to Bronze"
~~~

Expected: the new writer tests and existing cursor/telemetry tests pass, with no change to PostgreSQL extraction behavior.

---

### Task 4: Add the deterministic telemetry producer

**Files:**
- Create: src/portflow/streaming/producer.py
- Create: tests/unit/test_streaming_producer.py

**Interfaces:**

~~~python
from collections.abc import Callable, Iterable, Sequence
from typing import Protocol

DeliveryCallback = Callable[[object | None, object], None]

class ProducerClient(Protocol):
    def produce(
        self,
        topic: str,
        *,
        key: bytes,
        value: bytes,
        headers: Sequence[tuple[str, bytes]],
        callback: DeliveryCallback,
    ) -> None: pass

    def poll(self, timeout: float) -> int: pass
    def flush(self, timeout: float) -> int: pass

class ProducerDeliveryError(RuntimeError):
    """Raised when Redpanda does not acknowledge every produced event."""

@dataclass(frozen=True, slots=True)
class PublishReport:
    topic: str
    published_count: int

def publish_telemetry_events(
    events: Iterable[TelemetryEvent],
    *,
    producer: ProducerClient,
    topic: str,
    flush_timeout: float = 10.0,
) -> PublishReport: pass

def create_producer(config: StreamingConfig) -> ProducerClient: pass
~~~

create_producer lazily constructs confluent_kafka.Producer with producer_properties(config). publish_telemetry_events uses each event ID as the UTF-8 key, encode_telemetry_event(event) as the value, and telemetry_headers() as headers; it calls poll(0.0) after enqueueing and flush(flush_timeout) before returning. Any delivery callback error or non-zero remaining count raises ProducerDeliveryError.

- [ ] **Step 1: Write failing producer tests with a fake client.**

~~~python
def test_publish_uses_event_id_key_topic_and_headers() -> None:
    producer = FakeProducer()
    events = [valid_event()]

    report = publish_telemetry_events(
        events,
        producer=producer,
        topic="portflow.telemetry",
    )

    assert report == PublishReport(topic="portflow.telemetry", published_count=1)
    assert producer.calls[0].topic == "portflow.telemetry"
    assert producer.calls[0].key == b"evt-000042-000001"
    assert producer.calls[0].value == encode_telemetry_event(events[0])
    assert producer.calls[0].headers == list(telemetry_headers())
    assert producer.flush_calls == [10.0]


def test_publish_surfaces_delivery_error_without_success_report() -> None:
    producer = FakeProducer(delivery_error="broker rejected record")

    with pytest.raises(ProducerDeliveryError, match="broker rejected record"):
        publish_telemetry_events([valid_event()], producer=producer, topic="portflow.telemetry")
~~~

- [ ] **Step 2: Run producer tests before implementation.**

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_producer.py -q
~~~

Expected: FAIL because producer.py does not exist.

- [ ] **Step 3: Implement the protocol adapter and delivery callback.**

Keep the fakeable protocol free of confluent_kafka imports. Capture callback errors in a local list, call producer.poll(0.0) after each produce, and check the error list and flush remaining count before constructing PublishReport. Reject a negative flush_timeout with ValueError.

- [ ] **Step 4: Add the concrete client factory and run tests.**

In create_producer, import Producer inside the function and return it as the ProducerClient protocol. Run:

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_producer.py -q
./.venv/Scripts/python.exe -m ruff check src/portflow/streaming/producer.py tests/unit/test_streaming_producer.py
./.venv/Scripts/python.exe -m mypy src/portflow/streaming
~~~

- [ ] **Step 5: Commit the producer.**

~~~powershell
git add src/portflow/streaming/producer.py tests/unit/test_streaming_producer.py
git commit -m "feat: publish telemetry to Redpanda"
~~~

---

### Task 5: Add the manual-commit consumer

**Files:**
- Create: src/portflow/streaming/consumer.py
- Create: tests/unit/test_streaming_consumer.py

**Interfaces:**

~~~python
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

class ConsumerMessage(Protocol):
    def value(self) -> bytes | None: pass
    def headers(self) -> Sequence[tuple[str, bytes | None]] | None: pass
    def offset(self) -> int: pass

class ConsumerClient(Protocol):
    def subscribe(self, topics: Sequence[str]) -> None: pass
    def poll(self, timeout: float) -> ConsumerMessage | None: pass
    def commit(self, *, message: ConsumerMessage, asynchronous: bool) -> None: pass
    def close(self) -> None: pass

class StreamConsumerError(RuntimeError):
    """Raised when polling or Bronze publication cannot complete safely."""

class BronzeWriter(Protocol):
    def __call__(
        self,
        events: Sequence[TelemetryEvent],
        *,
        bronze_dir: Path,
        run_id: str,
    ) -> StreamBronzeWriteResult: pass

@dataclass(frozen=True, slots=True)
class ConsumeReport:
    consumed_count: int
    bronze_row_count: int
    committed_count: int
    batch_count: int

def consume_telemetry_stream(
    consumer: ConsumerClient,
    *,
    topic: str,
    bronze_dir: Path,
    run_id: str,
    batch_size: int,
    max_messages: int,
    writer: BronzeWriter = write_telemetry_bronze_batch,
    poll_timeout_seconds: float = 1.0,
    idle_timeout_seconds: float = 30.0,
) -> ConsumeReport: pass

def create_consumer(config: StreamingConfig) -> ConsumerClient: pass
~~~

The algorithm subscribes to the single topic, polls until max_messages, accumulates (event, message) pairs, decodes every message, writes a batch at batch_size or at max_messages, commits pending[-1][1] with asynchronous=False only after the writer returns, then clears the batch. Use time.monotonic for idle timeout. A partition-EOF message is treated as an empty poll; every other broker error raises StreamConsumerError.

A StreamValidationError, writer failure, or commit failure must leave the current batch uncommitted and must close the consumer in finally. A crash between writer success and offset commit may replay the batch. The concrete factory lazily constructs confluent_kafka.Consumer with consumer_properties(config).

- [ ] **Step 1: Write failing consumer tests with fake messages and clients.**

Add tests named test_commits_only_after_writer_succeeds, test_invalid_message_does_not_write_or_commit, test_writer_failure_does_not_commit, test_times_out_without_messages, and test_consumer_closes_on_success_and_failure. The success test records writer, then commit, then close:

~~~python
def test_commits_only_after_writer_succeeds(tmp_path: Path) -> None:
    consumer = FakeConsumer([message_for(valid_event())])
    calls: list[str] = []

    def writer(
        events: Sequence[TelemetryEvent],
        *,
        bronze_dir: Path,
        run_id: str,
    ) -> StreamBronzeWriteResult:
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

    assert report.committed_count == 1
    assert calls == ["writer", "commit"]
    assert consumer.closed is True
~~~

- [ ] **Step 2: Run consumer tests before implementation.**

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_consumer.py -q
~~~

Expected: FAIL because consumer.py does not exist.

- [ ] **Step 3: Implement batching, timeout, error, and close behavior.**

Use time.monotonic for timeout comparisons. Detect the concrete client's partition EOF sentinel through its error code without importing the client at module import time. Do not catch and suppress codec, writer, or commit exceptions. Call consumer.close in finally even when the first message is invalid.

- [ ] **Step 4: Run focused tests and static checks.**

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_consumer.py tests/unit/test_streaming_producer.py tests/unit/test_streaming_bronze.py -q
./.venv/Scripts/python.exe -m ruff check src/portflow/streaming tests/unit/test_streaming_consumer.py
./.venv/Scripts/python.exe -m mypy src/portflow/streaming src/portflow/ingestion
~~~

Expected: all fake-client tests pass and mypy has no errors.

- [ ] **Step 5: Commit the consumer.**

~~~powershell
git add src/portflow/streaming/consumer.py tests/unit/test_streaming_consumer.py
git commit -m "feat: consume telemetry into Bronze"
~~~

---

### Task 6: Add the opt-in Redpanda Compose service and local runners

**Files:**
- Modify: compose.yaml
- Modify: .env.example
- Create: scripts/run_stream_producer.py
- Create: scripts/run_stream_consumer.py
- Create: tests/unit/test_streaming_compose.py

**Interfaces:**

The Compose service is named redpanda, uses the pinned image docker.redpanda.com/redpandadata/redpanda:v26.2.2, exposes host port 19092, advertises localhost:19092 to host clients and redpanda:9092 to the Compose network, runs as one overprovisioned development node, has a healthcheck using bundled rpk, is under profiles: ["streaming"], and has no persistent named volume.

The producer runner accepts --seed and --count, defaults to 42 and 288, uses FIXTURE_START, TERMINAL_ID, and EQUIPMENT_ID from portflow.seed, calls generate_telemetry, create_producer, and publish_telemetry_events, and prints a sorted JSON PublishReport.

The consumer runner accepts required positive --max-messages, --run-id defaulting to stream-run-000042, and --bronze-dir defaulting to PORTFLOW_STREAM_BRONZE_DIR or data/bronze-stream. It calls create_consumer and consume_telemetry_stream, then prints a sorted JSON ConsumeReport.

- [ ] **Step 1: Write the Compose and runner tests before editing them.**

~~~python
def test_compose_keeps_redpanda_opt_in() -> None:
    compose = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "redpanda:" in compose
    assert "profiles:" in compose
    assert '"streaming"' in compose
    assert "docker.redpanda.com/redpandadata/redpanda:v26.2.2" in compose
    assert '"19092:19092"' in compose
    assert "--advertise-kafka-addr" in compose
~~~

Add runner tests that patch factory functions and assert --seed/--count and --max-messages/--run-id/--bronze-dir reach the public functions.

- [ ] **Step 2: Run the contract tests before implementation.**

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_compose.py -q
~~~

Expected: FAIL because the service and runners do not exist.

- [ ] **Step 3: Add the Redpanda service without changing PostgreSQL.**

~~~yaml
  redpanda:
    profiles: ["streaming"]
    image: docker.redpanda.com/redpandadata/redpanda:v26.2.2
    command:
      - redpanda
      - start
      - --mode
      - dev-container
      - --overprovisioned
      - --smp
      - "1"
      - --reserve-memory
      - "0M"
      - --check=false
      - --kafka-addr
      - internal://0.0.0.0:9092,external://0.0.0.0:19092
      - --advertise-kafka-addr
      - internal://redpanda:9092,external://localhost:19092
      - --rpc-addr
      - redpanda:33145
      - --advertise-rpc-addr
      - redpanda:33145
    ports:
      - "19092:19092"
    healthcheck:
      test: ["CMD", "rpk", "cluster", "health"]
      interval: 5s
      timeout: 5s
      retries: 20
~~~

- [ ] **Step 4: Implement the two bounded runners.**

Use argparse, dataclasses.asdict, and json.dumps with sort_keys=True. Do not add a daemon mode or a third streaming command. Runner errors must propagate as non-zero exits and must not write public data.

- [ ] **Step 5: Run contract, unit, and YAML checks, then commit.**

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_compose.py tests/unit/test_streaming_config.py tests/unit/test_streaming_codec.py -q
python -c "import pathlib, yaml; yaml.safe_load(pathlib.Path('compose.yaml').read_text(encoding='utf-8'))"
./.venv/Scripts/python.exe -m ruff check scripts/run_stream_producer.py scripts/run_stream_consumer.py tests/unit/test_streaming_compose.py
git add compose.yaml .env.example scripts/run_stream_producer.py scripts/run_stream_consumer.py tests/unit/test_streaming_compose.py
git commit -m "build: add local Redpanda streaming workflow"
~~~

---

### Task 7: Prove the real Redpanda round-trip in a separate CI check

**Files:**
- Create: tests/streaming/test_redpanda.py
- Create: scripts/verify_streaming.ps1
- Create: .github/workflows/streaming.yml
- Modify: pyproject.toml

**Interfaces:**

Register the strict pytest marker:

~~~toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--strict-markers"
markers = [
  "redpanda: requires a running local Redpanda broker",
]
~~~

Collect the real test under tests/streaming so the existing PostgreSQL autouse fixture is not applied. When PORTFLOW_REDPANDA_BROKERS is absent, skip with the exact reason PORTFLOW_REDPANDA_BROKERS is not set; start the streaming Compose profile.

The test uses a unique topic and group per run, publishes 12 deterministic events, consumes exactly 12, asserts the Bronze columns/row count/hash, creates minimal valid terminals and equipment reference partitions in the temporary Bronze root, and runs transform_bronze_to_silver with zero quarantined rows. Use confluent_kafka.admin.AdminClient and NewTopic to create the unique topic, TopicPartition plus a separate consumer committed call to assert the committed offset equals 12 after the Bronze write.

- [ ] **Step 1: Write the skipped/round-trip test before adding its implementation.**

~~~python
pytestmark = [
    pytest.mark.redpanda,
    pytest.mark.skipif(
        not os.environ.get("PORTFLOW_REDPANDA_BROKERS"),
        reason="PORTFLOW_REDPANDA_BROKERS is not set; start the streaming Compose profile",
    ),
]
~~~

Then add the real flow and assertions:

~~~python
events = generate_telemetry(
    seed=42,
    equipment_id=EQUIPMENT_ID,
    terminal_id=TERMINAL_ID,
    count=12,
    start_at=FIXTURE_START,
)
publish_report = publish_telemetry_events(events, producer=producer, topic=topic)
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
assert silver_report.quarantine_rows == 0
assert committed_offset == 12
~~~

- [ ] **Step 2: Run the test without a broker.**

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/streaming/test_redpanda.py -m redpanda -q
~~~

Expected: the test is skipped with the documented reason, not failed and not silently ignored.

- [ ] **Step 3: Implement the real broker fixture and assertions.**

Create the unique topic with one partition and replication factor one. Use the configured brokers, replace only topic/group in a copied StreamingConfig, publish with the production adapter, consume with the production adapter, and read the generated Parquet with Polars. Write minimal valid reference rows with the same Bronze metadata columns before invoking transform_bronze_to_silver. Delete the unique topic in a finally block when the AdminClient reports it exists.

- [ ] **Step 4: Add the focused PowerShell verification command.**

Create scripts/verify_streaming.ps1 with this control flow:

~~~powershell
$ErrorActionPreference = "Stop"
$previousBrokers = $env:PORTFLOW_REDPANDA_BROKERS
$hadBrokers = Test-Path Env:PORTFLOW_REDPANDA_BROKERS
$env:PORTFLOW_REDPANDA_BROKERS = "localhost:19092"
try {
    docker compose --profile streaming up -d --wait redpanda
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python -m uv run pytest tests/streaming/test_redpanda.py -m redpanda -v
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    docker compose --profile streaming down -v
    if ($hadBrokers) { $env:PORTFLOW_REDPANDA_BROKERS = $previousBrokers }
    else { Remove-Item Env:PORTFLOW_REDPANDA_BROKERS -ErrorAction SilentlyContinue }
}
~~~

- [ ] **Step 5: Add the separate GitHub Actions workflow.**

Create .github/workflows/streaming.yml with pull_request and push to main, contents: read, one Ubuntu job, Python 3.12, uv sync --extra dev --frozen, and the repository Compose profile. Use these steps:

~~~yaml
- name: Start Redpanda
  run: docker compose --profile streaming up -d --wait redpanda
- name: Run Redpanda round-trip
  env:
    PORTFLOW_REDPANDA_BROKERS: localhost:19092
  run: python -m uv run pytest tests/streaming/test_redpanda.py -m redpanda -v
- name: Stop Redpanda
  if: always()
  run: docker compose --profile streaming down -v
~~~

Keep ci.yml, scripts/verify_r2.ps1, and the Pages workflow's PostgreSQL-only behavior unchanged.

- [ ] **Step 6: Run focused tests and commit the broker verification.**

~~~powershell
./.venv/Scripts/python.exe -m pytest tests/streaming/test_redpanda.py -q
python -c "import pathlib, yaml; [yaml.safe_load(p.read_text(encoding='utf-8')) for p in pathlib.Path('.github/workflows').glob('*.yml')]"
./.venv/Scripts/python.exe -m ruff check tests/streaming
git add tests/streaming scripts/verify_streaming.ps1 .github/workflows/streaming.yml pyproject.toml
git commit -m "ci: verify Redpanda streaming round-trip"
~~~

Expected: the local test skips without a broker, workflow YAML parses, and static checks pass. Run scripts/verify_streaming.ps1 when Docker's Linux engine is available and record its result.

---

### Task 8: Document the local workflow and close PF-101

**Files:**
- Create: docs/runbooks/local-streaming.md
- Modify: README.md
- Modify: docs/product/BACKLOG.md
- Modify: CHANGELOG.md

**Interfaces:**

The runbook must preserve the public/static boundary and include these exact PowerShell commands:

~~~powershell
Set-Location C:/Users/aliha/PortFlow
docker compose --profile streaming up -d --wait redpanda
$env:PORTFLOW_REDPANDA_BROKERS = "localhost:19092"
python -m uv run python scripts/run_stream_producer.py --seed 42 --count 12
python -m uv run python scripts/run_stream_consumer.py --max-messages 12 --run-id stream-run-000042 --bronze-dir data/bronze-stream
python -m uv run pytest tests/streaming/test_redpanda.py -m redpanda -v
docker compose --profile streaming down -v
~~~

Explain that down -v removes only disposable local Redpanda data, the public browser remains static, and a malformed record fails without a Bronze write or committed offset. Document the PF-102 boundary: dedupe, late events, DLQ topics, and replay/backfill policy are not available in PF-101.

- [ ] **Step 1: Write the runbook and README link.**

Add a Local streaming entry under README's local data workspace section and link it to docs/runbooks/local-streaming.md. Include the topic, group, environment variables, port, cleanup, and troubleshooting for a missing Docker Linux engine or broker timeout.

- [ ] **Step 2: Write the PF-101 backlog and changelog entries.**

In docs/product/BACKLOG.md, add a completed PF-101 checkpoint with the final implementation commit hashes, update the post-V1 next action to PF-102 while explicitly stating that the documented main branch-protection rule remains outstanding, and preserve the existing V1 history. In CHANGELOG.md, add a dated post-V1 entry describing local telemetry streaming and its exclusions.

- [ ] **Step 3: Run documentation and whitespace checks, then commit.**

~~~powershell
git diff --check
git diff --stat
git add docs/runbooks/local-streaming.md README.md docs/product/BACKLOG.md CHANGELOG.md
git commit -m "docs: document PF-101 local streaming"
~~~

---

### Task 9: Run the complete verification checkpoint

**Files:**
- Read: all PF-101 implementation files and the approved spec/plan
- Verify: web/public/data remains unchanged

**Interfaces:**

No new interfaces are introduced. This task proves that the new local streaming slice does not regress the existing static product or deterministic pipeline.

- [ ] **Step 1: Check the lockfile and run all PF-101 unit tests.**

~~~powershell
python -m uv lock --check
./.venv/Scripts/python.exe -m pytest tests/unit/test_streaming_config.py tests/unit/test_streaming_codec.py tests/unit/test_streaming_bronze.py tests/unit/test_streaming_producer.py tests/unit/test_streaming_consumer.py tests/unit/test_streaming_compose.py -q
./.venv/Scripts/python.exe -m ruff check src scripts tests/unit/test_streaming_config.py tests/unit/test_streaming_codec.py tests/unit/test_streaming_bronze.py tests/unit/test_streaming_producer.py tests/unit/test_streaming_consumer.py tests/unit/test_streaming_compose.py
./.venv/Scripts/python.exe -m mypy src
~~~

Expected: all focused tests, Ruff, and mypy pass. If the existing Docker-backed integration suite is unavailable, preserve the exact Docker error in the final handoff and continue with broker-free checks; do not claim the real round-trip passed.

- [ ] **Step 2: Run the real Redpanda verification when Docker is available.**

~~~powershell
./scripts/verify_streaming.ps1
~~~

Expected: the Compose service reaches healthy, the producer publishes 12 events, the consumer writes three Bronze batches and commits 12 offsets, Silver accepts the stream plus references, and cleanup removes the disposable broker.

- [ ] **Step 3: Run the existing data and frontend gates.**

~~~powershell
./scripts/verify_r2.ps1
npm --prefix web test -- --run --maxWorkers=1
npm --prefix web run typecheck
npm --prefix web run build
git diff --exit-code -- web/public/data
~~~

Expected: the existing V1 pipeline, frontend tests, typecheck, build, and committed public-data assertion remain green. The React application and public snapshot files must not change.

- [ ] **Step 4: Inspect the final diff and status.**

~~~powershell
git diff --check
git status --short --branch
git log -10 --oneline --decorate
~~~

Expected: no whitespace errors, no untracked/generated files, and the final branch contains only focused PF-101 commits plus the previously committed design and plan documents.

## Completion Checkpoint

Stop after Task 9. Report the final commit hashes, focused unit count, whether the real Redpanda round-trip ran or was skipped because Docker was unavailable, the existing V1 gate result, and the fact that PF-102 remains the next streaming slice. Do not claim main branch protection was configured by this plan.
