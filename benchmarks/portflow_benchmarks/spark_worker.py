"""PySpark-side worker for the isolated benchmark container."""

import argparse
import json
import sys
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from time import perf_counter
from typing import Any, cast

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if __package__:
    from .canonical import canonicalize_rows, result_sha256  # noqa: E402
else:
    sys.path.insert(0, str(_PACKAGE_ROOT))
    from portflow_benchmarks.canonical import (  # type: ignore[import-not-found, no-redef]  # noqa: E402
        canonicalize_rows,
        result_sha256,
    )

_CANONICALIZE_ROWS = cast(
    Callable[[Iterable[Mapping[str, object]]], list[dict[str, object]]],
    canonicalize_rows,
)
_RESULT_SHA256 = cast(Callable[[Iterable[Mapping[str, object]]], str], result_sha256)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the PortFlow PySpark benchmark workload.")
    parser.add_argument("--fixture-dir", required=True)
    parser.add_argument("--window-start", required=True)
    parser.add_argument("--window-end", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=3)
    return parser


def _run_query(
    spark: Any,
    fixture_dir: str,
    window_start: str,
    window_end: str,
) -> list[dict[str, object]]:
    from pyspark.sql import functions as F  # type: ignore[import-not-found]

    frame = spark.read.parquet(fixture_dir)
    result = (
        frame.filter(
            (F.col("event_timestamp") >= F.to_timestamp(F.lit(window_start)))
            & (F.col("event_timestamp") < F.to_timestamp(F.lit(window_end)))
        )
        .groupBy("terminal_id", "state")
        .agg(
            F.count(F.lit(1)).alias("event_count"),
            F.sum(F.when(F.col("available"), F.lit(1)).otherwise(F.lit(0))).alias(
                "available_event_count"
            ),
            F.round(F.avg("load_percent"), 6).alias("average_load_percent"),
            F.round(F.avg("temperature_c"), 6).alias("average_temperature_c"),
        )
        .orderBy("terminal_id", "state")
    )
    rows = [cast(dict[str, object], row.asDict(recursive=True)) for row in result.collect()]
    return _CANONICALIZE_ROWS(rows)


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output_path = Path(args.output)
    try:
        from pyspark.sql import SparkSession

        startup_started = perf_counter()
        spark = SparkSession.builder.appName("portflow-pf105-benchmark").getOrCreate()
        startup_seconds = perf_counter() - startup_started
        warmup_started = perf_counter()
        rows: list[dict[str, object]] = []
        for _ in range(args.warmup):
            rows = _run_query(spark, args.fixture_dir, args.window_start, args.window_end)
        warmup_seconds = perf_counter() - warmup_started
        timed_seconds: list[float] = []
        for _ in range(args.repetitions):
            timed_started = perf_counter()
            rows = _run_query(spark, args.fixture_dir, args.window_start, args.window_end)
            timed_seconds.append(perf_counter() - timed_started)
        spark_version = str(spark.version)
        spark.stop()
        payload: dict[str, object] = {
            "status": "ok",
            "reason_code": None,
            "version": spark_version,
            "startup_seconds": startup_seconds,
            "warmup_seconds": warmup_seconds,
            "timed_seconds": timed_seconds,
            "rows_per_second": len(rows) / (sum(timed_seconds) / len(timed_seconds)),
            "result_sha256": _RESULT_SHA256(rows),
            "result_rows": rows,
        }
        _write_payload(output_path, payload)
        return 0
    except Exception:
        _write_payload(
            output_path,
            {
                "status": "error",
                "reason_code": "spark_worker_failed",
                "version": "unknown",
                "startup_seconds": 0.0,
                "warmup_seconds": 0.0,
                "timed_seconds": [],
                "rows_per_second": 0.0,
                "result_sha256": "",
                "result_rows": [],
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
