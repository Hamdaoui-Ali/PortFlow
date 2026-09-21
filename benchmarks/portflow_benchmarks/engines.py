"""DuckDB and Polars implementations of the shared benchmark workload."""

from collections.abc import Iterable, Mapping
from pathlib import Path
from time import perf_counter
from typing import Any, cast

import duckdb
import polars as pl

from .canonical import canonicalize_rows, result_sha256
from .models import EngineExecution, WorkloadSpec
from .workload import TELEMETRY_SUMMARY_WORKLOAD


def _fixture_glob(fixture_dir: Path) -> str:
    paths = sorted(fixture_dir.glob("*.parquet"))
    if not paths:
        raise ValueError("fixture must contain at least one Parquet file")
    return str(fixture_dir / "*.parquet")


def _as_int(value: object) -> int:
    return int(cast(Any, value))


def _as_float(value: object) -> float:
    return float(cast(Any, value))


def _normalize_rows(rows: Iterable[Mapping[str, object]]) -> tuple[dict[str, object], ...]:
    normalized: list[dict[str, object]] = []
    for row in rows:
        normalized.append(
            {
                "terminal_id": str(row["terminal_id"]),
                "state": str(row["state"]),
                "event_count": _as_int(row["event_count"]),
                "available_event_count": _as_int(row["available_event_count"]),
                "average_load_percent": _as_float(row["average_load_percent"]),
                "average_temperature_c": _as_float(row["average_temperature_c"]),
            }
        )
    return tuple(canonicalize_rows(normalized))


def _execution(
    *,
    name: str,
    version: str,
    startup_seconds: float,
    elapsed_seconds: float,
    rows: tuple[dict[str, object], ...],
) -> EngineExecution:
    rows_per_second = len(rows) / elapsed_seconds if elapsed_seconds > 0 else 0.0
    return EngineExecution(
        name=name,
        version=version,
        startup_seconds=startup_seconds,
        warmup_seconds=0.0,
        timed_seconds=(elapsed_seconds,),
        rows_per_second=rows_per_second,
        result_sha256=result_sha256(rows),
        result_rows=rows,
    )


def run_duckdb(fixture_dir: Path, workload: WorkloadSpec) -> EngineExecution:
    """Run the shared aggregation through an in-memory DuckDB connection."""
    fixture_glob = _fixture_glob(fixture_dir)
    startup_started = perf_counter()
    connection = duckdb.connect(database=":memory:")
    try:
        startup_seconds = perf_counter() - startup_started
        timed_started = perf_counter()
        result = connection.execute(
            TELEMETRY_SUMMARY_WORKLOAD.replace(
                "FROM telemetry_fixture",
                "FROM read_parquet(?)",
            ),
            [fixture_glob, workload.window_start, workload.window_end],
        )
        columns = [description[0] for description in result.description]
        raw_rows = [dict(zip(columns, values, strict=True)) for values in result.fetchall()]
        elapsed_seconds = perf_counter() - timed_started
        rows = _normalize_rows(raw_rows)
        return _execution(
            name="duckdb",
            version=duckdb.__version__,
            startup_seconds=startup_seconds,
            elapsed_seconds=elapsed_seconds,
            rows=rows,
        )
    finally:
        connection.close()


def run_polars(fixture_dir: Path, workload: WorkloadSpec) -> EngineExecution:
    """Run the shared aggregation through a Polars lazy Parquet scan."""
    fixture_glob = _fixture_glob(fixture_dir)
    startup_started = perf_counter()
    scan = pl.scan_parquet(fixture_glob)
    startup_seconds = perf_counter() - startup_started
    timed_started = perf_counter()
    result = (
        scan.filter(
            (pl.col("event_timestamp") >= pl.lit(workload.window_start))
            & (pl.col("event_timestamp") < pl.lit(workload.window_end))
        )
        .group_by(["terminal_id", "state"])
        .agg(
            pl.len().alias("event_count"),
            pl.col("available").cast(pl.Int64).sum().alias("available_event_count"),
            pl.col("load_percent").mean().round(6).alias("average_load_percent"),
            pl.col("temperature_c").mean().round(6).alias("average_temperature_c"),
        )
        .sort(["terminal_id", "state"])
        .collect()
    )
    elapsed_seconds = perf_counter() - timed_started
    rows = _normalize_rows(result.to_dicts())
    return _execution(
        name="polars",
        version=pl.__version__,
        startup_seconds=startup_seconds,
        elapsed_seconds=elapsed_seconds,
        rows=rows,
    )


def engine_version(engine_name: str) -> str:
    """Return the installed version for a supported host engine."""
    if engine_name == "duckdb":
        return duckdb.__version__
    if engine_name == "polars":
        return pl.__version__
    raise ValueError(f"unsupported engine: {engine_name}")


def execute_workload(
    engine_name: str,
    fixture_dir: Path,
    workload: WorkloadSpec,
) -> EngineExecution:
    """Dispatch one workload execution to a supported host engine."""
    if engine_name == "duckdb":
        return run_duckdb(fixture_dir, workload)
    if engine_name == "polars":
        return run_polars(fixture_dir, workload)
    raise ValueError(f"unsupported engine: {engine_name}")
