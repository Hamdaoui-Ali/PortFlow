# PF-104 Engineering Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an opt-in local Prometheus and Grafana stack that exposes bounded aggregate metrics from the PF-103 stream_runs SQLite state without changing stream delivery behavior.

**Architecture:** A dependency-free Python exporter opens the configured SQLite state file read-only and computes one scrape snapshot. Optional Compose services run the exporter, Prometheus, and Grafana; Prometheus scrapes only the exporter, and Grafana reads only Prometheus. The default Compose workflow, public site, and direct consumer CLI remain unchanged.

**Tech Stack:** Python 3.12 standard library, sqlite3, ThreadingHTTPServer, Prometheus text exposition format, Docker Compose profiles, Prometheus, Grafana, pytest, Ruff, mypy.

**Spec:** docs/superpowers/specs/2026-09-19-portflow-pf-104-observability-design.md

## Global Constraints

- Observe the PF-103 streaming path only; the PostgreSQL and batch pipeline are outside this slice.
- Read stream_runs as the source of truth; do not add per-message metrics, tracing, or new writes to the consumer hot path.
- Add one optional observability Compose profile containing a read-only PortFlow metrics exporter, Prometheus, and Grafana.
- Refresh the exporter view on each Prometheus scrape from the local SQLite state database.
- Keep the exporter dependency-free beyond Python's standard library.
- Never use run_id, error messages, raw payloads, broker addresses, or other unbounded values as metric labels.
- Bind published observability ports to loopback and document the stack as disposable local state.
- Direct CLI runs do not write stream_runs and therefore do not appear in PF-104 run metrics.
- Do not add a React route, public snapshot field, Pages artifact, hosted monitoring service, authentication system, alerting policy, or cloud dependency.
- The exporter must open SQLite in read-only mode and must not create directories, initialize schemas, update watermarks, or alter event/run state.
- web/public/data must remain byte-for-byte unchanged.

## Review Focus

- Missing state database: the exporter stays reachable, returns empty values, and reports state_store_available=0; pinned by Task 1 tests.
- Malformed timestamps or invalid stored statuses: the scrape reports collection failure instead of inventing partial metrics; pinned by Task 1 tests.
- A still-running latest run: duration uses the injected current UTC time and finished timestamp remains zero; pinned by Task 1 tests.
- Metric-cardinality leakage: run IDs, exception text, database paths, and arbitrary values never appear in labels or rendered exposition; pinned by Task 1 tests.
- Profile and mount safety: the default Compose startup is unchanged, the state mount is read-only, and published ports bind to loopback; pinned by Tasks 3 and 4 tests.

---

### Task 1: Read-only stream metrics snapshot (DYX-001)

**Goal:** Convert the existing stream_runs table into a deterministic typed snapshot and Prometheus exposition text without importing the heavier streaming state module.

**Dependencies:** None.

**Files:**
- Create: src/portflow/observability/__init__.py
- Create: src/portflow/observability/metrics.py
- Create: tests/unit/test_observability_metrics.py

**Interfaces:**
- Consumes: a Path to .stream-state.sqlite3 and an injected aware UTC datetime.
- Produces: StreamMetricsSnapshot, collect_stream_metrics(state_path, *, now), and render_prometheus(snapshot) for Task 2.

**Required public types and signatures:**

    from dataclasses import dataclass
    from datetime import datetime
    from pathlib import Path
    from typing import Literal

    StreamRunStatus = Literal["running", "succeeded", "failed"]

    @dataclass(frozen=True, slots=True)
    class StreamMetricsSnapshot:
        state_store_available: bool
        collection_success: bool
        runs_count: dict[StreamRunStatus, int]
        last_run_status: StreamRunStatus | None
        last_run_started_at: datetime | None
        last_run_finished_at: datetime | None
        last_run_duration_seconds: float
        consumed_messages_total: int
        bronze_rows_total: int
        committed_batches_total: int
        duplicate_messages_total: int
        late_messages_total: int
        dead_letters_total: int

    def collect_stream_metrics(
        state_path: Path,
        *,
        now: datetime,
    ) -> StreamMetricsSnapshot: ...

    def render_prometheus(snapshot: StreamMetricsSnapshot) -> str: ...

- [ ] **Step 1: Write the failing collector tests.**

Create a local SQLite fixture helper inside tests/unit/test_observability_metrics.py. The normal fixture must create exactly the PF-103 stream_runs columns and insert rows with run_id, status, ISO-8601 UTC timestamps, and the seven report counters. For the malformed-status test, use a separate deliberately malformed table with the same selected columns but without the PF-103 CHECK constraint, so the reader—not SQLite's writer validation—exercises the invalid-status path. Do not use StreamStateStore in this module; the exporter must stay independent of heavier streaming imports.

Add tests named:
- test_collect_missing_state_is_empty_and_does_not_create_file
- test_collect_sums_successful_counters_and_selects_latest_run
- test_running_latest_run_uses_injected_now_and_zero_finished_timestamp
- test_invalid_timestamp_or_status_marks_collection_unsuccessful
- test_collection_does_not_modify_read_only_state_file
- test_rendered_metrics_have_only_bounded_status_labels

The missing-file test must assert state_store_available=False, collection_success=False, all three status counts are zero, last_run_status is None, and the parent directory and SQLite file were not created.

The aggregate test must insert one succeeded row with counters 4, 3, 2, 1, 0, 0 and one later failed row with null counters. It must assert status counts running=0, succeeded=1, failed=1; latest status failed; latest duration 5.0 seconds; and aggregate totals 4 consumed, 3 Bronze rows, 2 committed batches, 1 duplicate, 0 late, 0 dead-letter.

The running-row test must start at 11:59:30 UTC, inject now=12:00:00 UTC, and assert duration 30.0 and no finished timestamp.

The invalid-row test must assert both state_store_available=False and collection_success=False. The read-only test must hash the SQLite file before and after collection. The exposition test must assert the documented status label line exists and that run_id, error_message, and a fixture run identifier do not appear in the output.

- [ ] **Step 2: Run the focused tests and verify they fail for the intended reason.**

Run:

    python -m uv run pytest tests/unit/test_observability_metrics.py -q

Expected: collection fails because portflow.observability.metrics and its public types do not exist yet.

- [ ] **Step 3: Implement the minimal read-only collector and renderer.**

Implement metrics.py with these rules:

1. Use sqlite3.connect(f"file:{state_path}?mode=ro", uri=True) and set row_factory=sqlite3.Row.
2. Query only stream_runs fields needed for the snapshot, including run_id solely as an internal tie-breaker.
3. Sort the latest row by started_at DESC, run_id DESC; never put run_id in the returned snapshot or exposition.
4. Parse timestamps with datetime.fromisoformat, require an aware timestamp, and normalize to UTC.
5. Sum only non-null counters. Failed rows with null counters add zero to aggregate totals without claiming that the failed run processed zero messages.
6. Clamp a negative clock difference to 0.0 if the injected clock is earlier than started_at.
7. Return an empty failure snapshot for FileNotFoundError, OSError, sqlite3.Error, TypeError, and ValueError; do not create a missing file or directory.
8. Render all three status label values in deterministic order and emit the documented HELP and TYPE lines.
9. Emit UTC timestamps as Unix seconds and emit 0 for an absent start or finish time.

Use a private helper to construct the empty failure snapshot so every failure path has exactly the same values. Keep the public module free of imports from portflow.streaming.state, pyarrow, or the Kafka client.

- [ ] **Step 4: Run the focused tests and static checks.**

Run:

    python -m uv run pytest tests/unit/test_observability_metrics.py -q
    python -m uv run ruff check src/portflow/observability tests/unit/test_observability_metrics.py
    python -m uv run mypy src/portflow/observability

Expected: all collector tests pass, Ruff reports no errors, and mypy reports no issues.

- [ ] **Step 5: Commit the collector.**

    git add src/portflow/observability tests/unit/test_observability_metrics.py
    git commit -m "feat: add read-only stream metrics collector"

**Expected result:** A deterministic, read-only StreamMetricsSnapshot and Prometheus renderer exist with no consumer or SQLite mutation.

---

### Task 2: HTTP metrics service (DYX-002)

**Goal:** Serve the Task 1 snapshot over HTTP and provide a module entry point for the Compose exporter service.

**Dependencies:** Task 1.

**Files:**
- Create: src/portflow/observability/server.py
- Create: tests/unit/test_observability_server.py

**Interfaces:**
- Consumes: collect_stream_metrics and render_prometheus from Task 1.
- Produces: main(argv), create_metrics_server(state_path, host, port), and serve_metrics(state_path, host, port) for Compose and the runbook.

**Required public signatures:**

    from collections.abc import Sequence
    from pathlib import Path
    from http.server import ThreadingHTTPServer

    def create_metrics_server(
        state_path: Path,
        *,
        host: str,
        port: int,
    ) -> ThreadingHTTPServer: ...

    def serve_metrics(
        state_path: Path,
        *,
        host: str,
        port: int,
    ) -> None: ...

    def main(argv: Sequence[str] | None = None) -> None: ...

- [ ] **Step 1: Write failing HTTP and CLI tests.**

Add a helper that starts create_metrics_server on 127.0.0.1 with port 0 in a daemon thread and stops it in finally. Add tests named:
- test_metrics_endpoint_returns_prometheus_text
- test_unknown_path_returns_not_found
- test_main_reads_state_path_host_and_port_from_environment

The metrics test must assert HTTP 200, a text/plain Prometheus content type, and a body containing portflow_stream_state_store_available 1. The unknown-path test must assert HTTP 404 for /health. The CLI test must set PORTFLOW_STREAM_STATE_PATH=custom/state.sqlite3, PORTFLOW_STREAM_METRICS_HOST=127.0.0.1, and PORTFLOW_STREAM_METRICS_PORT=9123, monkeypatch serve_metrics, call main([]), and assert the captured Path, host, and integer port.

- [ ] **Step 2: Run the server tests and verify the intended failure.**

    python -m uv run pytest tests/unit/test_observability_server.py -q

Expected: collection fails because portflow.observability.server does not exist yet.

- [ ] **Step 3: Implement the HTTP server and environment-backed entry point.**

Implement a small BaseHTTPRequestHandler that serves only GET /metrics, calls collect_stream_metrics(state_path, now=datetime.now(UTC)) for each request, returns HTTP 200 with Content-Type text/plain; version=0.0.4; charset=utf-8, returns 404 for every other path, and suppresses request logging. Store only state_path on a typed ThreadingHTTPServer subclass.

Implement main(argv) with these exact defaults:
- PORTFLOW_STREAM_STATE_PATH: data/bronze-stream/.stream-state.sqlite3
- PORTFLOW_STREAM_METRICS_HOST: 0.0.0.0
- PORTFLOW_STREAM_METRICS_PORT: 9108

Allow --state-path, --host, and --port command-line overrides. Parse the port as an integer and reject values outside 1..65535 through argparse. Add the module guard that calls main().

- [ ] **Step 4: Run focused tests and static checks.**

    python -m uv run pytest tests/unit/test_observability_metrics.py tests/unit/test_observability_server.py -q
    python -m uv run ruff check src/portflow/observability tests/unit/test_observability_*.py
    python -m uv run mypy src/portflow/observability

Expected: all exporter tests pass, Ruff reports no errors, and mypy reports no issues.

- [ ] **Step 5: Commit the HTTP service.**

    git add src/portflow/observability/server.py tests/unit/test_observability_server.py
    git commit -m "feat: expose stream metrics endpoint"

**Expected result:** A local /metrics endpoint serves scrape-time snapshots while preserving the missing-state and failure semantics from Task 1.

---

### Task 3: Optional Compose and Prometheus profile (DYX-003)

**Goal:** Run the exporter and Prometheus locally without changing the default PostgreSQL or streaming Compose profiles.

**Dependencies:** Task 2.

**Files:**
- Modify: compose.yaml
- Create: observability/prometheus.yml
- Modify: tests/unit/test_streaming_compose.py

**Interfaces:**
- Consumes: python -m portflow.observability.server from Task 2.
- Produces: Compose services named portflow-metrics and prometheus, profile observability, and scrape target portflow-metrics:9108 for Task 4.

- [ ] **Step 1: Write failing Compose contract tests.**

Extend tests/unit/test_streaming_compose.py with YAML parsing. Add tests named test_observability_profile_is_opt_in_and_read_only and test_prometheus_scrapes_only_portflow_metrics.

The first test must parse compose.yaml and assert:
- portflow-metrics and prometheus each have profiles=["observability"];
- portflow-metrics sets PORTFLOW_STREAM_STATE_PATH to /var/lib/portflow/.stream-state.sqlite3;
- at least one portflow-metrics volume ends with :ro;
- portflow-metrics publishes 127.0.0.1:9108:9108;
- prometheus publishes 127.0.0.1:9090:9090.

The second test must parse observability/prometheus.yml and assert global.scrape_interval is 5s and the only scrape target is portflow-metrics:9108 under job_name portflow-stream.

- [ ] **Step 2: Run the Compose tests and verify the intended failure.**

    python -m uv run pytest tests/unit/test_streaming_compose.py -q

Expected: the new tests fail because the observability services and Prometheus configuration do not exist yet; existing Redpanda tests remain passing.

- [ ] **Step 3: Add the exporter and Prometheus services.**

Add portflow-metrics to compose.yaml with profile observability, image python:3.12-alpine, working_dir /workspace, PYTHONPATH /workspace/src, PORTFLOW_STREAM_STATE_PATH /var/lib/portflow/.stream-state.sqlite3, command python -m portflow.observability.server --host 0.0.0.0 --port 9108, a read-only ./src:/workspace/src mount, a read-only ./data/bronze-stream:/var/lib/portflow mount, and loopback-only port 127.0.0.1:9108:9108.

Add a health check using the image's wget against http://127.0.0.1:9108/metrics. Add prometheus with profile observability, pinned image prom/prometheus:v2.54.1, read-only mount observability/prometheus.yml, disposable named volume prometheus_data, loopback-only port 127.0.0.1:9090:9090, and a dependency on portflow-metrics becoming healthy. Keep PostgreSQL and Redpanda definitions unchanged.

Create observability/prometheus.yml with exactly:

    global:
      scrape_interval: 5s
      evaluation_interval: 5s

    scrape_configs:
      - job_name: portflow-stream
        static_configs:
          - targets: ["portflow-metrics:9108"]

Declare prometheus_data as a top-level named volume. Do not add observability to the default service list, streaming profile, or CI quality-gate startup commands.

- [ ] **Step 4: Run Compose parsing and static checks.**

    python -m uv run pytest tests/unit/test_streaming_compose.py -q
    docker compose config
    docker compose --profile observability config
    python -m uv run ruff check tests/unit/test_streaming_compose.py

Expected: all Compose tests pass, both Compose configurations parse, and Ruff reports no errors. The default config must not start observability services, while the profile config must include them.

- [ ] **Step 5: Commit the Compose profile.**

    git add compose.yaml observability/prometheus.yml tests/unit/test_streaming_compose.py
    git commit -m "feat: add optional Prometheus profile"

**Expected result:** The exporter and Prometheus can be started explicitly with --profile observability, and the exporter can read the host stream directory without write access.

---

### Task 4: Grafana provisioning and starter dashboard (DYX-004)

**Goal:** Make the local metrics useful immediately through a checked-in Grafana data source and dashboard.

**Dependencies:** Task 3.

**Files:**
- Modify: compose.yaml
- Create: observability/grafana/provisioning/datasources/prometheus.yml
- Create: observability/grafana/provisioning/dashboards/default.yml
- Create: observability/grafana/dashboards/portflow-streaming.json
- Create: tests/unit/test_observability_config.py

**Interfaces:**
- Consumes: Prometheus at http://prometheus:9090 and metric names from Task 1.
- Produces: Grafana service named grafana, data source UID portflow-prometheus, and dashboard UID portflow-streaming.

- [ ] **Step 1: Write failing provisioning and dashboard tests.**

Create tests/unit/test_observability_config.py. The data source test must parse the YAML and assert apiVersion=1 and one non-editable proxy data source with name PortFlow Prometheus, type prometheus, uid portflow-prometheus, URL http://prometheus:9090, and isDefault=true.

The dashboard test must parse JSON and assert uid=portflow-streaming, plus panels titled State store availability, Run status, Latest run duration, Stream outcomes, and Latest run status. Collect all panel target expressions and assert that they include:
- portflow_stream_state_store_available
- portflow_stream_runs_count
- portflow_stream_last_run_duration_seconds
- portflow_stream_consumed_messages_total
- portflow_stream_dead_letters_total

- [ ] **Step 2: Run the provisioning tests and verify the intended failure.**

    python -m uv run pytest tests/unit/test_observability_config.py -q

Expected: collection or assertions fail because the Grafana provisioning files and service do not exist yet.

- [ ] **Step 3: Add Grafana provisioning and dashboard files.**

Create the data source file with one non-editable proxy data source:

    apiVersion: 1
    datasources:
      - name: PortFlow Prometheus
        type: prometheus
        uid: portflow-prometheus
        access: proxy
        url: http://prometheus:9090
        isDefault: true
        editable: false

Create the dashboard provider file with a read-only file provider rooted at /var/lib/grafana/dashboards and folder PortFlow.

Create portflow-streaming.json with UID portflow-streaming, title PortFlow streaming observability, refresh interval 5s, and panels titled exactly:
- State store availability, querying portflow_stream_state_store_available.
- Run status, querying portflow_stream_runs_count grouped by status.
- Latest run duration, querying portflow_stream_last_run_duration_seconds.
- Stream outcomes, querying all six aggregate outcome metrics from Task 1.
- Latest run status, querying portflow_stream_last_run_status grouped by status.

Do not include a panel or variable containing run_id, error_message, error_type, broker address, or state path.

Add grafana to the observability profile with pinned image grafana/grafana:11.2.0, loopback-only port 127.0.0.1:3000:3000, the two read-only provisioning/dashboard mounts, and disposable named volume grafana_data. Set GF_SECURITY_ADMIN_PASSWORD from the overridable Compose expression ${PORTFLOW_GRAFANA_ADMIN_PASSWORD:-portflow}. Do not expose Grafana beyond loopback.

- [ ] **Step 4: Run configuration tests and Compose parsing.**

    python -m uv run pytest tests/unit/test_observability_config.py tests/unit/test_streaming_compose.py -q
    docker compose --profile observability config
    python -m uv run ruff check tests/unit/test_observability_config.py

Expected: all tests pass, the profile parses, Grafana depends on Prometheus, and the dashboard contains only the bounded metric contract.

- [ ] **Step 5: Commit Grafana configuration.**

    git add compose.yaml observability/grafana tests/unit/test_observability_config.py
    git commit -m "feat: provision local streaming dashboard"

**Expected result:** A local Grafana instance opens with a preconfigured Prometheus source and a useful streaming-run dashboard.

---

### Task 5: Local observability runbook and repository references (DYX-005)

**Goal:** Make PF-104 repeatable for a repository owner without changing the existing PF-101/PF-103 workflow instructions.

**Dependencies:** Tasks 2, 3, and 4.

**Files:**
- Modify: docs/runbooks/local-streaming.md
- Modify: README.md
- Modify: CHANGELOG.md
- Create: tests/unit/test_observability_docs.py

**Interfaces:**
- Consumes: service names, ports, environment variables, and metrics endpoint from Tasks 2-4.
- Produces: a documented start/inspect/stop workflow and repository-level PF-104 completion references after verification.

- [ ] **Step 1: Write failing documentation-contract tests.**

Create tests/unit/test_observability_docs.py. Add tests named test_streaming_runbook_documents_pf104_start_inspect_and_cleanup and test_public_docs_keep_observability_local_only.

The runbook test must require:
- PF-104
- docker compose --profile streaming --profile observability up -d --wait
- http://127.0.0.1:9108/metrics
- http://127.0.0.1:9090
- http://127.0.0.1:3000
- PORTFLOW_GRAFANA_ADMIN_PASSWORD
- read-only
- stream_runs
- docker compose --profile observability down -v

The public-docs test must require PF-104, Prometheus, and Grafana in README.md, and PF-104 plus local wording in CHANGELOG.md.

- [ ] **Step 2: Run the documentation tests and verify the intended failure.**

    python -m uv run pytest tests/unit/test_observability_docs.py -q

Expected: assertions fail because the PF-104 runbook, README note, and changelog entry do not exist yet.

- [ ] **Step 3: Add the runbook section and repository references.**

Append an Optional engineering observability (PF-104) section after PF-103 in docs/runbooks/local-streaming.md. Document this start workflow:

    Set-Location C:/Users/aliha/PortFlow
    docker compose --profile streaming --profile observability up -d --wait redpanda portflow-metrics prometheus grafana
    Invoke-WebRequest http://127.0.0.1:9108/metrics

Document that the exporter reads data/bronze-stream/.stream-state.sqlite3 through a read-only mount, only Dagster-managed runs appear, and the default local Grafana password is portflow unless PORTFLOW_GRAFANA_ADMIN_PASSWORD is set before startup. Link to Prometheus at http://127.0.0.1:9090 and Grafana at http://127.0.0.1:3000.

Document cleanup with:

    docker compose --profile observability down -v

State that cleanup removes only disposable Prometheus/Grafana volumes and does not remove the stream Bronze directory or public snapshot. Add troubleshooting for state_store_available=0, a stopped Prometheus target, and an already-used loopback port.

Add a concise PF-104 local-only note to README.md. Add a dated changelog entry describing the optional exporter, Prometheus, Grafana dashboard, and bounded stream_runs contract. Leave the completed-checkpoint and current-next-action update in docs/product/BACKLOG.md for Task 6, after the complete verification gate passes.

- [ ] **Step 4: Run documentation tests and diff checks.**

    python -m uv run pytest tests/unit/test_observability_docs.py -q
    git diff --check

Expected: documentation assertions pass and the diff has no whitespace errors.

- [ ] **Step 5: Commit the documentation.**

    git add docs/runbooks/local-streaming.md README.md CHANGELOG.md tests/unit/test_observability_docs.py
    git commit -m "docs: document PF-104 observability"

**Expected result:** An engineer can start, inspect, and safely stop PF-104 without guessing paths, ports, credentials, or cleanup scope.

---

### Task 6: Full verification and local smoke check (DYX-006)

**Goal:** Prove PF-104 is isolated from the public snapshot and existing pipeline behavior, then verify the optional services together when Docker is available.

**Dependencies:** Tasks 1-5.

**Files:**
- Modify: none unless verification exposes a defect.
- Modify after verification: docs/product/BACKLOG.md
- Inspect: web/public/data, compose.yaml, observability/, src/portflow/observability/, and PF-104 tests.

**Interfaces:**
- Consumes: every PF-104 module, Compose file, dashboard, runbook, and test.
- Produces: passing quality-gate evidence and a clean public-data diff.

- [ ] **Step 1: Run the focused PF-104 suite.**

    python -m uv run pytest tests/unit/test_observability_metrics.py tests/unit/test_observability_server.py tests/unit/test_observability_config.py tests/unit/test_observability_docs.py tests/unit/test_streaming_compose.py -q

Expected: every focused test passes.

- [ ] **Step 2: Run the complete Python static and test gates.**

    python -m uv run ruff check .
    python -m uv run mypy src
    python -m uv run pytest tests/unit tests/integration tests/resilience tests/streaming -q

Expected: Ruff passes, mypy reports no issues, and the non-browser Python suite passes with only known environment-dependent skips.

- [ ] **Step 3: Verify Compose profiles and the public snapshot boundary.**

    docker compose config
    docker compose --profile observability config
    git diff --exit-code -- web/public/data
    git diff --check

Expected: both Compose configurations parse; the default configuration does not activate observability services; web/public/data has no diff; and whitespace validation passes.

- [ ] **Step 4: Run the optional local smoke check when Docker's Linux engine is available.**

    docker compose --profile streaming --profile observability up -d --wait redpanda portflow-metrics prometheus grafana
    try {
        Invoke-WebRequest http://127.0.0.1:9108/metrics
        Invoke-WebRequest http://127.0.0.1:9090/-/ready
        Invoke-WebRequest http://127.0.0.1:3000/api/health
    } finally {
        docker compose --profile observability down -v
    }

Expected: all three HTTP checks return success; the metrics response includes portflow_stream_state_store_available; cleanup stops only observability resources. If Docker is unavailable, record the existing environment limitation and retain unit/configuration evidence; do not broaden the task or delete repository state.

- [ ] **Step 5: Update the backlog only after verification passes.**

Update docs/product/BACKLOG.md by adding the PF-104 completed checkpoint, changing the current next action to PF-105, and keeping the main branch-protection follow-up visible. Do not mark PF-104 complete before Steps 1-4 pass.

- [ ] **Step 6: Run the final completion review and commit the backlog update.**

    git status --short
    git diff --stat
    git log -5 --oneline

Confirm that all PF-104 commits are present, no generated Grafana/Prometheus data is tracked, and no public snapshot or consumer safety code changed. Then commit the verified backlog update:

    git add docs/product/BACKLOG.md
    git commit -m "docs: close PF-104 observability"

**Expected result:** PF-104 is a local, opt-in, reproducible observability slice with verified tests, bounded metrics, documented cleanup, and no public-product regression.
