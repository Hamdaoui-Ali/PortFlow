# PF-106 Offline BigQuery Portability Lab

**Status:** Draft for review
**Date:** 2026-09-20
**Parent slice:** PF-105 reproducible engine benchmarks
**Scope decision:** Local-only GoogleSQL portability evidence and dry-run-ready artifacts

## Goal

Add a local portability lab that expresses the existing `overview_kpis`
analytical contract in BigQuery GoogleSQL, validates that SQL offline, and
produces deterministic artifacts that can later be submitted to `bq query
--dry_run` or the BigQuery Sandbox by an explicitly authorized workflow.

PF-106 is a portability-preparation and contract-evidence tool. It must not
contact Google Cloud, require credentials, or change the production DuckDB/dbt
pipeline.

## Intended outcome

The repository owner should be able to answer:

- Which GoogleSQL query represents the current `overview_kpis` contract?
- Which logical tables and BigQuery types does the query require?
- Does the query parse as BigQuery GoogleSQL without DuckDB-only constructs?
- Does the deterministic local fixture produce the same canonical result as the
  existing local Gold contract?
- Can the generated query and schema be handed to a future credentialed dry run
  without reconstructing the portability setup?

The result is an auditable local artifact bundle, not a claim that BigQuery has
executed the query or estimated bytes processed.

## Approved decisions

- Keep the production `analytics/models/` dbt project and existing Gold SQL
  unchanged.
- Add a reviewed GoogleSQL contract at
  `analytics/portability/bigquery/overview_kpis.sql`.
- Keep local portability code in a repository-only
  `labs/portflow_bigquery/` package; do not add it to the PortFlow wheel or
  `src/portflow/`.
- Generate a small deterministic fixture containing telemetry, movements,
  incidents, and alarms with the edge cases needed by `overview_kpis`.
- Use the existing local DuckDB/dbt Gold contract as the reference result for
  the same fixture.
- Validate the rendered query with a local BigQuery-dialect SQL parser and
  explicit checks for known DuckDB-only constructs. The parser is a development
  dependency, not a production runtime dependency.
- Generate only local, ignored artifacts below `.portability/bigquery/`.
- Record query, schema, fixture, and canonical-result hashes in a versioned
  manifest, together with `cloud_execution: "not_run"`.
- Include a future `bq query --use_legacy_sql=false --dry_run` command template
  in the manifest, but never invoke it in PF-106.
- Use explicit columns, UTC timestamps, stable ordering, six-decimal numeric
  canonicalization, and explicit null handling.
- Preserve current KPI semantics and known single-terminal assumptions for the
  compatibility fixture. Correcting business logic belongs to a separate task.
- Keep the public snapshot, Docker Compose services, streaming behavior,
  orchestration, observability, and UI unchanged.

## Non-goals

- No BigQuery API, `bq` process, Google Cloud SDK, account, project, dataset,
  credential, or network access.
- No actual BigQuery Sandbox execution or bytes-processed estimate.
- No `dbt-bigquery` adapter or BigQuery connection profile in the default
  environment.
- No upload to BigQuery, Cloud Storage, or another external service.
- No change to existing DuckDB Gold SQL, KPI definitions, public data, or
  `web/public/data`.
- No cloud performance comparison, cost claim, or production migration plan.
- No public UI, dashboard, route, design artifact, or user-facing product
  workflow.
- No automatic SQL transpilation or query-plan rewriting.
- No committed generated fixture, result, or dry-run output.

## Architecture

```text
committed GoogleSQL contract + schema mapping
                    |
                    v
        deterministic local fixture generator
             /                    \
            v                      v
 rendered GoogleSQL          Silver Parquet fixture
            |                      |
            v                      v
 local BigQuery parser      local dbt/DuckDB Gold reference
             \                    /
              v                  v
             canonical result comparison
                       |
                       v
     manifest + query/schema/result dry-run bundle
```

The portability lab owns fixture generation, query rendering, dialect
validation, local reference execution, canonicalization, manifest writing, and
manifest verification. It is an engineering evidence tool and remains outside
the production package boundary.

### Repository package boundary

Create a focused repository-local `labs/portflow_bigquery/` package. It is
invoked from the repository root with:

```text
python -m labs.portflow_bigquery run
python -m labs.portflow_bigquery verify --manifest .portability/bigquery/manifest.json
```

The `run` command creates a deterministic fixture, renders the committed
GoogleSQL template, runs local parsing and reference checks, and writes the
manifest. The `verify` command validates an existing bundle without contacting
an external service.

The CLI may accept explicit output, project, dataset, and fixture parameters,
but defaults must remain small, deterministic, and offline. Project and dataset
values are only rendered into the future command template; they are not used to
authenticate or connect.

### GoogleSQL contract

The committed query must use logical table placeholders that can be rendered as
fully qualified BigQuery table identifiers. It must retain the current
`overview_kpis` output fields and semantics while replacing DuckDB-specific
expressions with GoogleSQL equivalents, including:

- `COUNTIF(...)` for conditional counts;
- `TIMESTAMP_DIFF(..., SECOND)` for timestamp duration calculations;
- `SAFE_DIVIDE(...)` or equivalent explicit zero-denominator handling;
- `COALESCE(...)` and explicit casts where the result type needs to be stable;
- explicit `ORDER BY` columns for deterministic result ordering.

The query must not contain local file readers, Jinja references that remain
unrendered, DuckDB `FILTER (...)` aggregates, DuckDB `date_diff(...)`, or
implicit `SELECT *` in the contract output. Table and column names must be
explicit and match the committed schema mapping.

The explicit output contract is:

```text
terminal_id, source_period_start, source_period_end,
available_intervals, scheduled_intervals, active_intervals,
available_time_minutes, resolved_incident_count, repair_minutes,
qualifying_failure_count, operating_hours, throughput,
average_dwell_minutes, availability, utilization, mttr_minutes,
mtbf_hours, active_incidents, critical_alarms
```

The current model's single-terminal incident association is a compatibility
constraint for this lab. PF-106 must make that constraint visible in the
manifest or runbook rather than silently broadening or correcting it.

### Fixture contract

The generator writes a small deterministic Silver-shaped Parquet fixture with
one primary terminal (`TM-001`) and enough rows to exercise the current KPI
rules:

| Logical source | Required coverage |
| --- | --- |
| `telemetry_events` | available, unavailable, and active states; fixed UTC cadence; period boundaries |
| `container_movements` | complete entry/exit pair and incomplete pair |
| `incidents` | resolved and open incidents; critical and non-critical severity; null unresolved timestamp |
| `alarms` | critical and non-critical alarms inside and outside the telemetry period |

The fixture includes the minimum columns required by the existing staging
models, including source metadata fields needed by dbt. Values are generated
from a fixed seed and written with stable UTC timestamps. Its metadata includes
the generator version, row counts by table, schema, relative file layout, and a
logical SHA-256 hash independent of Parquet file ordering.

The local reference runner points `PORTFLOW_SILVER_DIR` and
`PORTFLOW_GOLD_DB` at temporary paths, runs the existing local dbt Gold build,
and reads the resulting `overview_kpis` rows. It must not use the checked-in
public snapshot as the reference input.

### Canonical result contract

The reference result and expected portability result use the existing
`overview_kpis` field names and stable row ordering by `terminal_id`. The
canonicalizer must:

- preserve strings and integers without coercion to text;
- serialize UTC timestamps consistently;
- round finite floating-point metrics to six decimal places;
- preserve `NULL` as JSON `null`;
- reject non-finite numeric values and unexpected fields;
- hash canonical JSON with sorted keys and a terminating newline.

The expected result hash is derived from the local Gold reference. PF-106 does
not execute the GoogleSQL query locally; the parser and contract checks prove
dialect readiness, while the local Gold run proves the fixture's expected
PortFlow semantics. A later cloud-enabled task must add actual BigQuery result
comparison.

## Artifact and manifest contract

Generated files live below the ignored `.portability/bigquery/` directory:

```text
.portability/bigquery/
  manifest.json
  overview_kpis.sql
  schema.json
  expected-result.json
  input-fingerprint.json
  fixture/
    telemetry_events/*.parquet
    container_movements/*.parquet
    incidents/*.parquet
    alarms/*.parquet
```

The manifest has a versioned schema similar to:

```json
{
  "schema_version": 1,
  "task": "PF-106",
  "dialect": "bigquery_google_sql",
  "execution_mode": "offline",
  "cloud_execution": "not_run",
  "query": {
    "path": "overview_kpis.sql",
    "sha256": "...",
    "parser": "bigquery",
    "dry_run_command": "bq query --use_legacy_sql=false --dry_run ..."
  },
  "schema": {
    "path": "schema.json",
    "sha256": "..."
  },
  "fixture": {
    "generator_version": "1",
    "tables": 4,
    "rows": {},
    "sha256": "..."
  },
  "reference": {
    "engine": "duckdb_dbt",
    "result_rows": 1,
    "result_sha256": "..."
  },
  "verification": {
    "status": "ok",
    "reason_code": null,
    "verifier_version": "1"
  }
}
```

The exact schema is validated by tests. Manifests must not contain credentials,
absolute developer paths, arbitrary exception text, raw environment dumps, or
unbounded per-row payloads. Failure manifests may contain only bounded reason
codes and safe, stable metadata.

## Safety and failure behavior

- The CLI has no cloud-enabled mode in PF-106 and must not import a cloud client
  or inspect credential environment variables.
- Output, fixture, and manifest paths must resolve below `.portability/`.
  Traversal and external output paths fail closed.
- Any SQL parse failure, forbidden token, schema mismatch, missing fixture,
  non-deterministic hash, dbt reference failure, or result mismatch exits
  non-zero with a stable reason code.
- Verification must not modify `web/public/data`, the repository's normal
  `data/` tree, Docker Compose state, or any existing generated snapshot.
- A failed run must not be reported as a successful portability result. Partial
  artifacts may be left under the ignored output directory, but their manifest
  status must be `error` and must not contain raw subprocess output.

## Testing and verification

Before PF-106 is complete:

- unit tests cover deterministic multi-table fixture generation, schema mapping,
  query rendering, BigQuery-dialect parsing, forbidden DuckDB construct checks,
  canonical result hashing, path containment, manifest validation, and bounded
  failure reasons;
- an integration test runs the local dbt Gold reference on the generated
  fixture, writes a manifest, and verifies the expected result hash;
- a repeat-run test confirms identical fixture, query, schema, result, and
  manifest hashes;
- tamper tests change the SQL, schema, fixture, and expected result separately
  and assert that verification fails for the correct reason code;
- tests prove the generated bundle does not touch public data or the default
  Compose configuration;
- the runbook documents installation, local commands, artifact fields, the
  future dry-run handoff, the compatibility constraint, and cleanup;
- Ruff, mypy, the focused portability tests, and the full existing Python suite
  pass; and
- the browser suite is unchanged because PF-106 has no UI surface.

## Documentation and repository boundaries

- `docs/runbooks/bigquery-portability.md` documents the offline workflow and
  clearly distinguishes generated dry-run-ready artifacts from an actual
  BigQuery dry run.
- `.gitignore` ignores `.portability/` and generated fixture files.
- No generated portability artifact is copied into `web/public/data`.
- The PF-106 entry in `docs/product/BACKLOG.md` is marked complete only after
  the specification, implementation, tests, runbook, and verification evidence
  are committed.

## References

- [BigQuery query syntax](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/query-syntax)
- [BigQuery aggregate functions and `COUNTIF`](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/aggregate_functions)
- [BigQuery timestamp functions and `TIMESTAMP_DIFF`](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/timestamp_functions)
- [Running queries and dry runs](https://docs.cloud.google.com/bigquery/docs/running-queries)
- [BigQuery Sandbox](https://docs.cloud.google.com/bigquery/docs/sandbox)

## Rollout and follow-up

PF-106 remains local, explicit, disposable, and credential-free. Its artifact
bundle becomes the input contract for a future cloud-enabled task without making
cloud access part of ordinary development or CI.

PF-107 may reuse the deterministic fixture and canonicalization approach for a
Databricks Free Edition Delta/PySpark lab. PF-108 may add an explicitly
time-limited cloud comparison, with separate approval, credentials, cost
guardrails, and a separate workflow. Neither follow-up is included in PF-106.
