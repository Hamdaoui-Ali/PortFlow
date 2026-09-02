# R2 trusted local pipeline

**Status:** verified locally on 2026-09-03

R2 keeps the public product web-accessible as static HTML, CSS, JavaScript, and
versioned JSON. PostgreSQL is disposable local/CI state; DuckDB is a local build
artifact. Neither database is reachable from the browser.

## Checkpoint commits

| Slice | Commit |
|---|---|
| PF-008 operational schema | `8deb3b4` |
| PF-009 deterministic seed | `ab35b6a` |
| PF-010 cursor-safe Bronze | `e290238` |
| PF-011 Silver validation | `0572fc0` |
| PF-012 DuckDB/dbt Gold | `16c9e69` |
| PF-013 complete public export | `f6c7226` |
| dbt artifact hygiene | `d625750` |

## Reproducibility evidence

- Python: 3.12.4 through `uv`; database image: `postgres:16-alpine`.
- Seed: `42`; source period: `2026-09-02T00:00:00Z` through
  `2026-09-02T23:55:00Z`.
- Seed counts: terminals 1, equipment 1, telemetry 288, alarms 3, incidents 2,
  maintenance orders 2, and container movements 8.
- Bronze rows: 305. Silver rows: 305. Quarantine rows: 0. The reconciliation
  invariant is `Bronze = Silver + quarantine`.
- dbt build: 9 models and 22 data tests passed.
- The committed `demo-v2` manifest records lowercase SHA-256 hashes for
  `overview`, `equipment`, `incidents`, `event_replay`, and `quality`. A second
  pipeline run produces identical public file hashes.

## Release commands

    docker compose up -d --wait postgres
    python -m uv sync --extra dev --frozen
    npm --prefix web ci
    ./scripts/verify_r2.ps1
    docker compose down

The gate runs migrations, deterministic seed, all seven incremental extracts,
Silver validation, dbt Gold, schema-validated JSON export, Python tests, lint,
type checks, frontend tests, and the production build. A failed stage writes only
to a disposable staging directory and cannot replace the previous manifest.

## Explicit exclusions

Redpanda/Kafka, Dagster, Prometheus/Grafana, MinIO, Spark, Terraform, cloud
databases, public streaming, authentication, and a public write API remain out
of scope. They are R3+ decisions, not hidden runtime dependencies.
