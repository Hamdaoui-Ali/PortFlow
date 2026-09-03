"""Incremental PostgreSQL extraction into immutable Bronze Parquet partitions."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
import psycopg
from psycopg.sql import SQL, Identifier

from portflow.ingestion.cursor import CursorStore, SourceCursor

_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=UTC)
_METADATA_COLUMNS = (
    "source_table",
    "extraction_run_id",
    "source_updated_at",
    "extracted_at",
)


@dataclass(frozen=True, slots=True)
class TableSpec:
    """Allow-listed source table columns used by the extractor."""

    table_name: str
    primary_key: str
    columns: tuple[str, ...]


TABLE_SPECS: dict[str, TableSpec] = {
    "terminals": TableSpec(
        table_name="terminals",
        primary_key="terminal_id",
        columns=("terminal_id", "name", "timezone_name", "created_at", "updated_at"),
    ),
    "equipment": TableSpec(
        table_name="equipment",
        primary_key="equipment_id",
        columns=(
            "equipment_id",
            "terminal_id",
            "equipment_type",
            "commissioning_date",
            "created_at",
            "updated_at",
        ),
    ),
    "telemetry_events": TableSpec(
        table_name="telemetry_events",
        primary_key="event_id",
        columns=(
            "event_id",
            "schema_version",
            "equipment_id",
            "terminal_id",
            "event_timestamp",
            "ingestion_timestamp",
            "state",
            "available",
            "load_percent",
            "temperature_c",
            "created_at",
            "updated_at",
        ),
    ),
    "alarms": TableSpec(
        table_name="alarms",
        primary_key="alarm_id",
        columns=(
            "alarm_id",
            "equipment_id",
            "severity",
            "code",
            "opened_at",
            "cleared_at",
            "created_at",
            "updated_at",
        ),
    ),
    "incidents": TableSpec(
        table_name="incidents",
        primary_key="incident_id",
        columns=(
            "incident_id",
            "equipment_id",
            "severity",
            "status",
            "opened_at",
            "resolved_at",
            "root_cause",
            "created_at",
            "updated_at",
        ),
    ),
    "maintenance_orders": TableSpec(
        table_name="maintenance_orders",
        primary_key="maintenance_order_id",
        columns=(
            "maintenance_order_id",
            "equipment_id",
            "status",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ),
    ),
    "container_movements": TableSpec(
        table_name="container_movements",
        primary_key="movement_id",
        columns=(
            "movement_id",
            "terminal_id",
            "equipment_id",
            "movement_type",
            "container_ref",
            "event_timestamp",
            "created_at",
            "updated_at",
        ),
    ),
}


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Outcome of one incremental table extraction."""

    table_name: str
    row_count: int
    logical_row_count: int
    partition_path: Path | None
    content_sha256: str | None
    next_cursor: SourceCursor | None


def _source_cursor(value: object, primary_key: object) -> SourceCursor:
    if not isinstance(value, datetime):
        raise TypeError("source updated_at must be a datetime")
    if not isinstance(primary_key, str):
        raise TypeError("source primary key must be a string")
    return SourceCursor(value, primary_key)


def _query_batch(
    connection: psycopg.Connection[Any],
    spec: TableSpec,
    source_cursor: SourceCursor | None,
    batch_size: int,
) -> list[tuple[Any, ...]]:
    columns = SQL(", ").join(Identifier(column) for column in spec.columns)
    statement = SQL(
        "select {} from {} where ({}, {}) > (%s, %s) "
        "order by {}, {} limit %s"
    ).format(
        columns,
        Identifier(spec.table_name),
        Identifier("updated_at"),
        Identifier(spec.primary_key),
        Identifier("updated_at"),
        Identifier(spec.primary_key),
    )
    updated_at = source_cursor.updated_at if source_cursor is not None else _EPOCH_UTC
    primary_key = source_cursor.primary_key if source_cursor is not None else ""
    with connection.cursor() as cursor:
        cursor.execute(statement, (updated_at, primary_key, batch_size))
        return cursor.fetchall()


def _cursor_slug(cursor: SourceCursor) -> str:
    timestamp = cursor.updated_at.astimezone(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"{timestamp}-{cursor.primary_key}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_batch(
    rows: list[tuple[Any, ...]],
    *,
    spec: TableSpec,
    bronze_dir: Path,
    run_id: str,
    next_cursor: SourceCursor,
) -> tuple[Path, str]:
    """Write, validate, hash, and atomically publish one batch."""
    row_dicts: list[dict[str, object]] = []
    updated_index = spec.columns.index("updated_at")
    extraction_index = (
        spec.columns.index("ingestion_timestamp")
        if "ingestion_timestamp" in spec.columns
        else updated_index
    )
    extracted_at_value = rows[-1][extraction_index]
    if not isinstance(extracted_at_value, datetime):
        raise TypeError("source extraction timestamp must be a datetime")
    extracted_at = extracted_at_value + timedelta(seconds=2)
    for row in rows:
        values = dict(zip(spec.columns, row, strict=True))
        source_updated_at = values["updated_at"]
        if not isinstance(source_updated_at, datetime):
            raise TypeError("source updated_at must be a datetime")
        values.update(
            {
                "source_table": spec.table_name,
                "extraction_run_id": run_id,
                "source_updated_at": source_updated_at,
                "extracted_at": extracted_at,
            }
        )
        row_dicts.append(values)

    expected_columns = [*spec.columns, *_METADATA_COLUMNS]
    frame = pl.DataFrame(row_dicts).select(expected_columns)
    if frame.height != len(rows) or frame.columns != expected_columns:
        raise RuntimeError(f"Bronze schema validation failed for {spec.table_name}")

    staging_dir = bronze_dir / ".staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    target_path = (
        bronze_dir
        / spec.table_name
        / f"date={next_cursor.updated_at.astimezone(UTC).date().isoformat()}"
        / f"part-{_cursor_slug(next_cursor)}.parquet"
    )
    staging_path = staging_dir / f"{target_path.name}.tmp"
    try:
        frame.write_parquet(staging_path, compression="zstd")
        staged_frame = pl.read_parquet(staging_path)
        if staged_frame.height != len(rows) or staged_frame.columns != expected_columns:
            raise RuntimeError(f"Bronze file validation failed for {spec.table_name}")
        content_sha256 = _sha256(staging_path)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            if _sha256(target_path) != content_sha256:
                raise ValueError(f"existing Bronze partition hash mismatch: {target_path}")
            staging_path.unlink(missing_ok=True)
        else:
            staging_path.replace(target_path)
    finally:
        staging_path.unlink(missing_ok=True)
    return target_path, content_sha256


def _existing_partition_summary(bronze_dir: Path, table_name: str) -> tuple[int, str | None]:
    table_dir = bronze_dir / table_name
    paths = sorted(table_dir.rglob("*.parquet")) if table_dir.exists() else []
    if not paths:
        return 0, None

    logical_row_count = 0
    digest = hashlib.sha256()
    for path in paths:
        frame = pl.read_parquet(path)
        logical_row_count += frame.height
        digest.update(path.relative_to(bronze_dir).as_posix().encode("utf-8"))
        digest.update(b"\n")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return logical_row_count, digest.hexdigest()


def extract_table(
    connection: psycopg.Connection[Any],
    *,
    table_name: str,
    cursor_store: CursorStore,
    bronze_dir: Path,
    run_id: str,
    batch_size: int = 1000,
) -> ExtractionResult:
    """Extract rows after the saved cursor and publish immutable Parquet."""
    if table_name not in TABLE_SPECS:
        raise ValueError(f"unsupported source table: {table_name}")
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    if not run_id:
        raise ValueError("run_id must not be empty")

    spec = TABLE_SPECS[table_name]
    source_cursor = cursor_store.load().get(table_name)
    extracted_row_count = 0
    last_partition: Path | None = None
    last_cursor = source_cursor

    while True:
        rows = _query_batch(connection, spec, source_cursor, batch_size)
        if not rows:
            break
        next_cursor = _source_cursor(
            rows[-1][spec.columns.index("updated_at")],
            rows[-1][spec.columns.index(spec.primary_key)],
        )
        partition_path, _ = _write_batch(
            rows,
            spec=spec,
            bronze_dir=bronze_dir,
            run_id=run_id,
            next_cursor=next_cursor,
        )

        cursors = cursor_store.load()
        cursors[table_name] = next_cursor
        cursor_store.save(cursors)
        extracted_row_count += len(rows)
        last_partition = partition_path
        last_cursor = next_cursor
        source_cursor = next_cursor
        if len(rows) < batch_size:
            break

    logical_row_count, content_sha256 = _existing_partition_summary(bronze_dir, table_name)
    return ExtractionResult(
        table_name=table_name,
        row_count=extracted_row_count,
        logical_row_count=logical_row_count,
        partition_path=last_partition,
        content_sha256=content_sha256,
        next_cursor=last_cursor,
    )
