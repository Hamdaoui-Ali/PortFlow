"""Deterministic telemetry-shaped Parquet fixture generation."""

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import polars as pl

from portflow.domain.models import EquipmentState  # type: ignore[import-untyped]

from .models import FixtureMetadata, FixtureSpec
from .paths import reject_reparse_components

FIXTURE_COLUMNS = (
    "event_id",
    "equipment_id",
    "terminal_id",
    "event_timestamp",
    "state",
    "available",
    "load_percent",
    "temperature_c",
)
_STATES = tuple(state.value for state in EquipmentState)
_CHUNK_ROWS = 1_000_000
_FIXTURE_START = datetime(2026, 1, 1, tzinfo=UTC)


def _state_expression(row_index: pl.Expr, seed: int) -> pl.Expr:
    state_index = (row_index + seed) % len(_STATES)
    expression: Any = pl.when(state_index == 0).then(pl.lit(_STATES[0]))
    for index, state in enumerate(_STATES[1:], start=1):
        expression = expression.when(state_index == index).then(pl.lit(state))
    return cast(pl.Expr, expression.otherwise(pl.lit(_STATES[-1])))


def _build_frame(start: int, rows: int, seed: int) -> pl.DataFrame:
    row_index = pl.col("row_index")
    frame = pl.DataFrame({"row_index": pl.arange(start, start + rows, eager=True)})
    state_index = (row_index + seed) % len(_STATES)
    return frame.select(
        pl.format(
            "evt-{}-{}",
            (row_index // 1_000_000).cast(pl.String).str.zfill(6),
            (row_index % 1_000_000).cast(pl.String).str.zfill(6),
        ).alias("event_id"),
        pl.format(
            "EQ-{}",
            (row_index % 32).cast(pl.String).str.zfill(3),
        ).alias("equipment_id"),
        pl.format(
            "TM-{}",
            ((row_index % 4) + 1).cast(pl.String).str.zfill(3),
        ).alias("terminal_id"),
        (pl.lit(_FIXTURE_START) + pl.duration(minutes=5) * row_index).alias("event_timestamp"),
        _state_expression(row_index, seed).alias("state"),
        (state_index < 3).alias("available"),
        (((row_index * 17 + seed) % 10001) / 100.0).cast(pl.Float64).alias("load_percent"),
        (
            -20.0 + (((row_index * 29 + seed) % 17001) / 100.0)
        ).cast(pl.Float64).alias("temperature_c"),
    )


def _canonical_fixture_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, float):
        return round(value, 6)
    return value


def _canonical_fixture_rows(rows: Iterable[dict[str, object]]) -> Iterable[bytes]:
    for row in rows:
        values = [_canonical_fixture_value(row[column]) for column in FIXTURE_COLUMNS]
        yield json.dumps(
            values,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")


def logical_fixture_hash(path: Path) -> str:
    """Hash sorted logical rows so physical Parquet layout does not matter."""
    parquet_paths = sorted(path.rglob("*.parquet")) if path.is_dir() else [path]
    if not parquet_paths or any(not parquet_path.is_file() for parquet_path in parquet_paths):
        raise ValueError("fixture must contain at least one Parquet file")
    frames = [pl.read_parquet(parquet_path) for parquet_path in parquet_paths]
    frame = pl.concat(frames, how="vertical").select(FIXTURE_COLUMNS).sort(list(FIXTURE_COLUMNS))
    digest = hashlib.sha256()
    for payload in _canonical_fixture_rows(frame.iter_rows(named=True)):
        digest.update(payload)
        digest.update(b"\n")
    return digest.hexdigest()


def generate_fixture(spec: FixtureSpec, output_dir: Path) -> FixtureMetadata:
    """Generate one deterministic Parquet fixture and return its metadata."""
    reject_reparse_components(
        output_dir,
        message="fixture output path must not contain symbolic links or reparse points",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for parquet_path in output_dir.glob("part-*.parquet"):
        parquet_path.unlink()
    file_count = 0
    for start in range(0, spec.rows, _CHUNK_ROWS):
        row_count = min(_CHUNK_ROWS, spec.rows - start)
        output_path = output_dir / f"part-{file_count:06d}.parquet"
        _build_frame(start, row_count, spec.seed).write_parquet(
            output_path,
            compression=spec.compression,
        )
        file_count += 1
    parquet_paths = sorted(output_dir.glob("part-*.parquet"))
    return FixtureMetadata(
        seed=spec.seed,
        rows=spec.rows,
        generator_version=spec.generator_version,
        compression=spec.compression,
        fixture_dir=output_dir,
        file_count=file_count,
        bytes=sum(path.stat().st_size for path in parquet_paths),
        logical_sha256=logical_fixture_hash(output_dir),
        schema=FIXTURE_COLUMNS,
    )
