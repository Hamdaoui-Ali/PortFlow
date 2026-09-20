# PF-105 Reproducible Engine Benchmarks Implementation Plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` when independent implementation tasks can be delegated safely; otherwise use `superpowers:executing-plans` and complete each task in order.

**Goal:** Add a reproducible, local benchmark harness that compares DuckDB, Polars, and an isolated PySpark runner on the same deterministic telemetry-shaped Parquet fixture, with validated machine-readable evidence.

**Architecture:** Keep the benchmark package repository-local and outside the production wheel. Run DuckDB and Polars in the host Python environment. Run PySpark only through a separately pinned Docker Compose worker. Share one engine-neutral workload, canonicalize results before hashing, and record bounded timing and availability metadata.

**Tech Stack:** Python 3.12, Polars, DuckDB, PyArrow/Parquet, PySpark in Docker, pytest, Ruff, mypy, and PowerShell-friendly CLI commands.

**Spec:** `docs/superpowers/specs/2026-09-19-portflow-pf-105-benchmarks-design.md`

## Global implementation constraints

- Keep the feature local-only. Do not add a public API, production pipeline stage, cloud dependency, or default service to the top-level Compose file.
- Use deterministic fixture generation and a logical fixture hash so equivalent data remains identifiable across Parquet writers.
- Use one shared workload contract and one canonical result format. Engine-specific output must not become the comparison result.
- Use one warmup and three timed repetitions by default. Keep startup timing separate from query timing.
- Keep benchmark output under `.benchmarks/`; generated fixtures, reports, Spark output, and logs must be ignored.
- Do not modify Gold transformations, streaming behavior, public snapshot generation, or PF-104 telemetry changes.
- Do not include raw exception text, secrets, absolute paths, per-row payloads, or unbounded diagnostic output in reports.

## Review focus before implementation

- Fixture determinism, schema fidelity, domain bounds, and logical hashing.
- DuckDB and Polars semantic equivalence, including UTC boundaries, null behavior, rounding, grouping, and ordering.
- Spark isolation, immutable image pinning, read-only fixture/code mounts, and bounded failure handling.
- Timing/report validation and separation of unavailable engines from successful measurements.
- The generated-data boundary: no public data or committed generated benchmark artifacts.

## Task 1: Add deterministic benchmark fixture and canonical primitives

**Files:**
- Create `benchmarks/__init__.py`.
- Create `benchmarks/portflow_benchmarks/__init__.py`.
- Create `benchmarks/portflow_benchmarks/models.py`.
- Create `benchmarks/portflow_benchmarks/fixture.py`.
- Create `benchmarks/portflow_benchmarks/canonical.py`.
- Create `tests/unit/test_benchmark_fixture.py`.
- Create `tests/unit/test_benchmark_canonical.py`.

**Interfaces:**
- `FixtureSpec(seed: int, rows: int, generator_version: str = "1", compression: str = "zstd")`.
- `FixtureMetadata` with `seed`, `rows`, `generator_version`, `compression`, `fixture_dir`, `file_count`, `bytes`, `logical_sha256`, and `schema`.
- `generate_fixture(spec: FixtureSpec, output_dir: Path) -> FixtureMetadata`.
- `logical_fixture_hash(path: Path) -> str`.
- `WorkloadSpec` with timezone-aware UTC `window_start` and `window_end`.
- `canonicalize_rows(rows) -> list[dict[str, object]]` and `result_sha256(rows) -> str`.

**TDD steps:**
1. Write failing tests for a deterministic 32-row fixture, exact telemetry columns, domain bounds, invalid row counts and seeds, canonical sorting, six-decimal numeric rounding, stable hashes, and invalid timestamps and windows.
2. Run `python -m pytest tests/unit/test_benchmark_fixture.py tests/unit/test_benchmark_canonical.py -q`; confirm the new tests fail because the modules do not exist.
3. Implement the smallest deterministic generator using the existing telemetry contract. Use these formulas:
   - `event_id = evt-{row_index // 1_000_000:06d}-{row_index % 1_000_000:06d}`.
   - `equipment_id = EQ-{row_index % 32:03d}` and `terminal_id = TM-{row_index % 4 + 1:03d}`.
   - `event_timestamp = 2026-01-01T00:00:00Z + row_index * five minutes`.
   - `state = existing state at (row_index + seed) modulo 5`.
   - `available = false` for `UNAVAILABLE` and `MAINTENANCE`, otherwise true.
   - `load_percent = ((row_index * 17 + seed) modulo 10001) / 100.0`.
   - `temperature_c = -20 + ((row_index * 29 + seed) modulo 17001) / 100.0`.
4. Write Zstd Parquet with Polars, one file through one million rows and deterministic chunking thereafter. Make the logical hash independent of file ordering and Parquet metadata.
5. Run the focused tests, then `python -m ruff check benchmarks tests/unit/test_benchmark_fixture.py tests/unit/test_benchmark_canonical.py` and `python -m mypy benchmarks`.

**Commit:** `feat: add deterministic benchmark fixture`

## Task 2: Implement DuckDB and Polars workload adapters

**Files:**
- Create `benchmarks/portflow_benchmarks/workload.py`.
- Create `benchmarks/portflow_benchmarks/engines.py`.
- Create `tests/unit/test_benchmark_workload.py`.
- Create `tests/integration/test_benchmark_engines.py`.

**Interfaces:**
- `TELEMETRY_SUMMARY_WORKLOAD` containing the engine-neutral workload definition.
- `run_duckdb(fixture_dir, workload) -> EngineExecution`.
- `run_polars(fixture_dir, workload) -> EngineExecution`.
- `engine_version(engine_name) -> str`.
- `execute_workload(engine_name, fixture_dir, workload) -> EngineExecution`.

**TDD steps:**
1. Write tests with a 1,000-row fixture that assert the exact result fields: `terminal_id`, `state`, `event_count`, `available_event_count`, `average_load_percent`, and `average_temperature_c`.
2. Assert DuckDB and Polars produce the same canonical result hash, integer counts, six-decimal averages, deterministic ordering, and a changed result for a narrower UTC window.
3. Run the focused tests and confirm failure before adding adapters.
4. Implement the exact workload contract:
   ```sql
   SELECT
     terminal_id,
     state,
     COUNT(*) AS event_count,
     SUM(CASE WHEN available THEN 1 ELSE 0 END) AS available_event_count,
     ROUND(AVG(load_percent), 6) AS average_load_percent,
     ROUND(AVG(temperature_c), 6) AS average_temperature_c
   FROM telemetry_fixture
   WHERE event_timestamp >= :window_start
     AND event_timestamp < :window_end
   GROUP BY terminal_id, state
   ORDER BY terminal_id, state
   ```
5. Use a read-only in-memory DuckDB connection with parameterized timestamps. Use a Polars lazy scan with the same half-open UTC filter, grouping, aggregation, rounding, and ordering.
6. Run the focused tests, Ruff, and mypy for the new package.

**Commit:** `feat: benchmark DuckDB and Polars equivalence`

## Task 3: Add the isolated PySpark runner

**Files:**
- Create `benchmarks/spark/compose.yaml`.
- Create `benchmarks/portflow_benchmarks/spark_worker.py`.
- Create `benchmarks/portflow_benchmarks/spark_runner.py`.
- Create `tests/unit/test_benchmark_spark_config.py`.

**Interfaces:**
- `run_pyspark(fixture_dir, workload, output_dir) -> EngineExecution`.
- Worker arguments: `--fixture-dir`, `--window-start`, `--window-end`, `--output`, `--warmup`, and `--repetitions`.
- `EngineExecution` fields: `name`, `version`, `startup_seconds`, `warmup_seconds`, `timed_seconds`, `rows_per_second`, `result_sha256`, `status`, and `reason_code`.

**TDD and image-pinning steps:**
1. Resolve an official Spark image before writing Compose:
   ```text
   docker pull apache/spark:4.0.0-python3
   docker image inspect apache/spark:4.0.0-python3 --format "{{index .RepoDigests 0}}"
   ```
2. Commit the returned immutable digest as `apache/spark@sha256:<returned-digest>`. If that tag is unavailable, use an official tag exposed by the successful pull; do not commit an unverified digest.
3. Write tests that assert the service is named `pyspark`, the image uses `@sha256:`, fixture and code mounts are read-only, the benchmark output mount is writable, there are no ports or persistent volumes, and the top-level `compose.yaml` is unchanged.
4. Add tests for local `spark-submit`, bounded output, and bounded reason codes without requiring Docker in ordinary unit tests.
5. Implement one Compose service invoking the worker. Mount only the fixture and benchmark code read-only plus `.benchmarks/spark` as the writable output directory.
6. Make the worker use Spark for the same aggregation and the standard-library canonicalizer for the same result hash. Measure one warmup and three repetitions and return bounded unavailable or failure codes.
7. Make the host runner validate that requested paths stay below `.benchmarks`, invoke `docker compose -f benchmarks/spark/compose.yaml run --rm pyspark`, and never expose raw subprocess errors in the report.
8. Run the Spark configuration tests and Ruff. Skip only tests that explicitly require an unavailable Docker daemon or image; do not install PySpark into the main environment.

**Commit:** `feat: isolate PySpark benchmark runner`

## Task 4: Add timing, report validation, and CLI orchestration

**Files:**
- Create `benchmarks/portflow_benchmarks/timing.py`.
- Create `benchmarks/portflow_benchmarks/report.py`.
- Create `benchmarks/portflow_benchmarks/runner.py`.
- Create `benchmarks/portflow_benchmarks/cli.py`.
- Create `benchmarks/portflow_benchmarks/__main__.py`.
- Create `tests/unit/test_benchmark_timing.py`.
- Create `tests/unit/test_benchmark_report.py`.
- Create `tests/unit/test_benchmark_cli.py`.

**Interfaces and behavior:**
- `DEFAULT_WARMUPS = 1` and `DEFAULT_REPETITIONS = 3`.
- `summarize_timings(samples) -> TimingSummary` computes median and p95 from timed samples only, and rejects empty or negative samples.
- `validate_report(report) -> None` rejects absolute paths, unknown engines, missing hashes, row-count mismatches, unbounded reason codes, invalid schema versions, and malformed timing fields.
- `run_benchmark(profile, engines, warmups, repetitions, report_path) -> BenchmarkReport`.
- `write_report(report, path) -> None` writes stable, versioned JSON.
- `main(argv) -> int` supports `run` and `verify`.

**TDD steps:**
1. Write tests for median and p95, warmup exclusion, empty and negative timing rejection, valid three-engine reports, invalid absolute paths, unknown engines, missing hashes, row mismatches, unbounded reasons, CLI help, and verify return codes.
2. Use fake adapters in unit tests so Docker is never required.
3. Implement profiles exactly as `smoke=10_000`, `small=100_000`, `medium=1_000_000`, and `large=5_000_000`.
4. Make the default command equivalent to `python -m benchmarks.portflow_benchmarks run --profile smoke --engines duckdb,polars --warmups 1 --repetitions 3`.
5. Require an explicit PySpark engine selection for full comparisons. If a requested engine is unavailable, write a bounded `unavailable` status and reason code, preserve the report, and exit nonzero.
6. Exclude run IDs, raw exception messages, secrets, absolute paths, and per-row payloads from the report.
7. Implement `__main__.py` as:
   ```python
   from .cli import main

   raise SystemExit(main())
   ```
8. Run all benchmark tests, CLI help, Ruff, and mypy.

**Commit:** `feat: add benchmark report and CLI`

## Task 5: Document usage and protect generated artifacts

**Files:**
- Update `.gitignore` with `.benchmarks/`.
- Create `docs/runbooks/benchmarks.md`.
- Update the relevant README section.
- Update `CHANGELOG.md`.
- Create `tests/unit/test_benchmark_docs.py`.

**TDD steps:**
1. Write documentation tests that require the ignored artifact directory, the four profiles, DuckDB, Polars, and PySpark commands, Docker and pinned-image guidance, report verification, cleanup, unavailability behavior, and the statement that benchmark data is not public data.
2. Document these commands:
   ```text
   python -m benchmarks.portflow_benchmarks run --profile smoke --engines duckdb,polars
   python -m benchmarks.portflow_benchmarks verify --report .benchmarks/reports/latest.json
   python -m benchmarks.portflow_benchmarks run --profile medium --engines duckdb,polars,pyspark
   Remove-Item .benchmarks -Recurse -Force
   ```
3. Explain deterministic fixture identity, host-specific timing, Spark prerequisites, bounded unavailable results, report validation, and the fact that no generated benchmark artifacts are committed.
4. Run the documentation tests and `git diff --check`.

**Commit:** `docs: document PF-105 benchmarks`

## Task 6: Run the full verification gate and close the backlog item

**Files:**
- Update `docs/product/BACKLOG.md` only after all implementation and verification checks pass.

**Verification steps:**
1. Run the complete PF-105-focused test list and ensure any Spark skip is explicitly caused by missing Docker or image availability.
2. Run `python -m ruff check .`.
3. Run `python -m mypy src`.
4. Run the full non-browser suite with `python -m pytest -q`.
5. Run the host smoke benchmark:
   ```text
   python -m benchmarks.portflow_benchmarks run --profile smoke --engines duckdb,polars --report .benchmarks/reports/smoke.json
   python -m benchmarks.portflow_benchmarks verify --report .benchmarks/reports/smoke.json
   ```
6. Run the Docker Compose configuration check and a small all-engine benchmark. If Docker or the pinned image is unavailable, keep the bounded unavailable result and document the environmental limitation; do not install PySpark into the production environment.
7. Confirm public data generation is unchanged, generated benchmark files are ignored, and `git status --short` contains only intended source, test, and documentation changes.
8. Update the backlog with PF-105 complete, the checkpoint, spec, plan, and commit references, the next action PF-106, the completed post-V1 row, and unchanged branch-protection expectations.

**Commit:** `docs: close PF-105 benchmark evidence`

## Final handoff

Before claiming completion, run the verification commands above and inspect their exit codes and relevant summaries. Then request a code review using `superpowers:requesting-code-review`, and use `superpowers:verification-before-completion` before reporting the branch as complete.
