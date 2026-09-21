"""Optional Dagster orchestration for bounded local stream consumption."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict, cast

from dagster import OpExecutionContext, job, op

from portflow.streaming.config import StreamingConfig
from portflow.streaming.consumer import (
    ConsumerClient,
    ConsumeReport,
    consume_telemetry_stream,
    create_consumer,
)
from portflow.streaming.producer import ProducerClient, create_producer
from portflow.streaming.state import StreamRunInputs, StreamStateStore

logger = logging.getLogger(__name__)

ConsumerFactory = Callable[[StreamingConfig], ConsumerClient]
ProducerFactory = Callable[[StreamingConfig], ProducerClient]
StateStoreFactory = Callable[[Path], StreamStateStore]


class StreamConsumerOpConfig(TypedDict):
    """Dagster config values for one manually triggered consumer run."""

    topic: str
    bronze_dir: str
    batch_size: int
    max_messages: int
    allowed_lateness_seconds: int
    poll_timeout_seconds: float
    idle_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class StreamConsumerJobConfig:
    """Explicit non-secret inputs for one Dagster-managed consumer run."""

    topic: str
    bronze_dir: Path
    batch_size: int
    max_messages: int
    allowed_lateness_seconds: int
    poll_timeout_seconds: float = 1.0
    idle_timeout_seconds: float = 30.0


@op(
    name="consume_stream",
    config_schema={
        "topic": str,
        "bronze_dir": str,
        "batch_size": int,
        "max_messages": int,
        "allowed_lateness_seconds": int,
        "poll_timeout_seconds": float,
        "idle_timeout_seconds": float,
    },
)
def consume_stream_op(context: OpExecutionContext) -> None:
    """Run the bounded stream consumer using Dagster's run identifier."""
    config = cast(StreamConsumerOpConfig, context.op_config)
    job_config = StreamConsumerJobConfig(
        topic=config["topic"],
        bronze_dir=Path(config["bronze_dir"]),
        batch_size=config["batch_size"],
        max_messages=config["max_messages"],
        allowed_lateness_seconds=config["allowed_lateness_seconds"],
        poll_timeout_seconds=config["poll_timeout_seconds"],
        idle_timeout_seconds=config["idle_timeout_seconds"],
    )
    report = execute_stream_consumer_run(
        run_id=context.run_id,
        job_config=job_config,
        env_config=StreamingConfig.from_env(),
    )
    context.log.info(
        "Stream run completed: consumed=%d, bronze_rows=%d, committed=%d, "
        "batches=%d, duplicates=%d, late=%d, dead_letters=%d",
        report.consumed_count,
        report.bronze_row_count,
        report.committed_count,
        report.batch_count,
        report.duplicate_count,
        report.late_count,
        report.dead_letter_count,
    )


@job
def stream_consumer_job() -> None:
    """Manually run one bounded telemetry consumer invocation."""
    consume_stream_op()


def execute_stream_consumer_run(
    *,
    run_id: str,
    job_config: StreamConsumerJobConfig,
    env_config: StreamingConfig,
    consumer_factory: ConsumerFactory = create_consumer,
    producer_factory: ProducerFactory = create_producer,
    state_store_factory: StateStoreFactory = StreamStateStore,
) -> ConsumeReport:
    """Execute one consumer run and persist its Dagster lifecycle metadata."""
    _validate_run_id(run_id)
    _validate_job_config(job_config)
    effective_config = replace(
        env_config,
        topic=job_config.topic,
        batch_size=job_config.batch_size,
        allowed_lateness_seconds=job_config.allowed_lateness_seconds,
    )
    if effective_config.topic == effective_config.dlq_topic:
        raise ValueError("source and dead-letter topics must differ")

    state_store = state_store_factory(job_config.bronze_dir / ".stream-state.sqlite3")
    consumer: ConsumerClient | None = None
    consumer_call_entered = False
    primary_error: BaseException | None = None
    try:
        try:
            state_store.start_run(
                run_id=run_id,
                inputs=StreamRunInputs(
                    topic=job_config.topic,
                    bronze_dir=job_config.bronze_dir,
                    batch_size=job_config.batch_size,
                    max_messages=job_config.max_messages,
                    allowed_lateness_seconds=job_config.allowed_lateness_seconds,
                    poll_timeout_seconds=job_config.poll_timeout_seconds,
                    idle_timeout_seconds=job_config.idle_timeout_seconds,
                ),
            )
        except BaseException as exc:
            primary_error = exc
            raise
        try:
            consumer = consumer_factory(effective_config)
            dead_letter_producer = producer_factory(effective_config)
            consumer_call_entered = True
            report = consume_telemetry_stream(
                consumer,
                topic=effective_config.topic,
                bronze_dir=job_config.bronze_dir,
                run_id=run_id,
                batch_size=effective_config.batch_size,
                max_messages=job_config.max_messages,
                dead_letter_producer=dead_letter_producer,
                dead_letter_topic=effective_config.dlq_topic,
                allowed_lateness_seconds=effective_config.allowed_lateness_seconds,
                state_store=state_store,
                poll_timeout_seconds=job_config.poll_timeout_seconds,
                idle_timeout_seconds=job_config.idle_timeout_seconds,
            )
        except BaseException as exc:
            primary_error = exc
            _record_failure_preserving_primary(state_store, run_id, exc)
            raise

        try:
            state_store.record_run_success(
                run_id=run_id,
                report=report,
                finished_at=_utc_now(),
            )
        except BaseException as exc:
            primary_error = exc
            raise
        return report
    finally:
        cleanup_error: Exception | None = None
        if consumer is not None and not consumer_call_entered:
            try:
                consumer.close()
            except Exception as exc:
                cleanup_error = exc
        try:
            state_store.close()
        except Exception as exc:
            if cleanup_error is None:
                cleanup_error = exc
        if cleanup_error is not None:
            if primary_error is not None:
                logger.warning(
                    "stream cleanup failed after primary error for run %s: %s",
                    run_id,
                    cleanup_error,
                )
            else:
                raise cleanup_error


def _record_failure_preserving_primary(
    state_store: StreamStateStore,
    run_id: str,
    error: BaseException,
) -> None:
    try:
        state_store.record_run_failure(
            run_id=run_id,
            error_type=type(error).__name__,
            error_message=str(error),
            finished_at=_utc_now(),
        )
    except Exception as metadata_error:
        logger.warning(
            "could not record failed stream run %s: %s",
            run_id,
            metadata_error,
        )


def _validate_run_id(run_id: str) -> None:
    if not run_id.strip():
        raise ValueError("run_id must not be empty")


def _validate_job_config(config: StreamConsumerJobConfig) -> None:
    if not config.topic.strip():
        raise ValueError("topic must not be empty")
    if config.batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    if config.max_messages <= 0:
        raise ValueError("max_messages must be greater than zero")
    if config.allowed_lateness_seconds < 0:
        raise ValueError("allowed_lateness_seconds must not be negative")
    if config.poll_timeout_seconds < 0:
        raise ValueError("poll_timeout_seconds must not be negative")
    if config.idle_timeout_seconds < 0:
        raise ValueError("idle_timeout_seconds must not be negative")


def _utc_now() -> datetime:
    return datetime.now(UTC)
