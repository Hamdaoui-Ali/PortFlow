# Local benchmark runbook

PF-105 provides an opt-in, local comparison of the PortFlow telemetry workload across
DuckDB, Polars, and PySpark. The benchmark is an engineering evidence tool. It does not
change the application pipeline, the public snapshot, or the static browser.

## Scope and artifact boundary

Benchmark data is deterministic synthetic test data, not public data. Generated fixtures,
reports, and Spark output live under `.benchmarks/`, which is ignored by Git.
Generated benchmark artifacts are not committed and must not be copied into
`web/public/data`.

The fixture generator records a logical hash (SHA-256) over canonical rows. Re-running the
same profile uses the same seed, generator version, schema, and workload window, so result
hashes can be compared across engines. This is host-specific timing: CPU, memory, filesystem,
Docker, Python, and background load affect the measured seconds. Use timings to compare
engines on the same machine and environment, not as a hosted performance promise.

## Profiles

| Profile | Input rows | Intended use |
| --- | ---: | --- |
| `smoke` | 10,000 | Fast local or CI check |
| `small` | 100,000 | Developer comparison |
| `medium` | 1,000,000 | Evidence run |
| `large` | 5,000,000 | Explicit capacity experiment |

The default timing protocol performs one warm-up and three timed repetitions. Use the
smoke profile first when checking a new environment.

## Prerequisites

Install the repository's normal Python development dependencies. DuckDB and Polars run
on the host. PySpark runs in Docker through the Compose file at
`benchmarks/spark/compose.yaml`; a running Docker daemon is required for that engine.

The Spark image is pinned by digest:

`apache/spark@sha256:a89782d90529a623fc4471cdddb0f9c32d6eed10a81b256a80207b23c3b1df00`

The Compose runner mounts only `.benchmarks/fixtures`, `benchmarks`, and
`.benchmarks/spark`. It does not expose a port or mount the public data directory.

## Run the benchmark

Run the host engines:

```text
python -m benchmarks.portflow_benchmarks run --profile smoke --engines duckdb,polars
```

Run the medium comparison, including the isolated PySpark engine:

```text
python -m benchmarks.portflow_benchmarks run --profile medium --engines duckdb,polars,pyspark
```

The command writes a versioned JSON report to
`.benchmarks/reports/latest.json` unless `--report` supplies another path.
The report contains fixture identity, workload identity, engine versions, startup/warm-up/timed
measurements, median and p95 seconds, input rows per second, result row count, and canonical
result hashes. Raw telemetry payloads and absolute local paths are not included.

Successful engines must produce the same canonical result hash. A mismatch is recorded as
an error rather than silently treated as a performance result.

## Verify a report

Validate the report shape and require every selected engine to have status `ok`:

```text
python -m benchmarks.portflow_benchmarks verify --report .benchmarks/reports/latest.json
```

The `run` command returns success when all selected engines succeed. If an engine is
unavailable or fails, it still writes bounded metadata such as `docker_unavailable`,
`spark_timeout`, or `engine_execution_failed`; the command returns a non-zero
status. `verify` also returns non-zero for a report containing an unavailable or failed
engine. This keeps missing optional tooling visible without exposing subprocess output in the
report.

If Docker is unavailable, run the DuckDB and Polars comparison by omitting `pyspark`.
The host-engine report remains useful and the PySpark result is intentionally not substituted
with a host implementation.

## Cleanup

Benchmark artifacts are disposable. Remove them from the worktree after an experiment:

```text
Remove-Item .benchmarks -Recurse -Force
```

On a POSIX shell, the equivalent is `rm -rf .benchmarks` after confirming the current
directory is the PortFlow worktree. Never use benchmark output as public application data.
