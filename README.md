# PortFlow

PortFlow is a public container-terminal operations control tower backed by a reproducible local data-engineering pipeline. It converts deterministic simulated operations data into tested analytical snapshots and publishes a static web application with no always-on backend.

## V1 boundary

- Public delivery: static HTML, CSS, JavaScript, and versioned JSON snapshots.
- Local processing: Python, PostgreSQL, Parquet, DuckDB, and dbt Core.
- Data status: simulated terminal operations data, never represented as a live commercial feed.
- Cost boundary: no required billing account, payment card, public API, database, broker, or server.

## Product documents

- [Enhanced product study](PORTFLOW_ENHANCED_PRODUCT_STUDY.md)
- [Approved design](docs/superpowers/specs/2026-09-02-portflow-zero-cost-web-product-design.md)
- [V1 backlog](docs/product/BACKLOG.md)
- [Cost evidence](docs/product/cost-evidence.md)
- [First public-slice plan](docs/superpowers/plans/2026-09-02-portflow-first-public-slice.md)

Implementation begins with one deterministic equipment-availability KPI rendered from a versioned public snapshot.

## Local data workspace

The public site remains static and reads versioned JSON only. For local development, PortFlow includes a loopback-only API that connects the existing PostgreSQL pipeline to the **Data Health** page. Use it to seed demo data, import validated JSON records, and refresh the published snapshot without editing source files.

Follow the complete [local development runbook](docs/runbooks/local-development.md). The browser never connects directly to PostgreSQL, and the hosted/static site intentionally shows **Local API unavailable** because it has no database connection.

For the opt-in Kafka-compatible telemetry path, follow the [local Redpanda streaming runbook](docs/runbooks/local-streaming.md). PF-102 adds restart-safe event state, bounded lateness, and a canonical dead-letter topic while writing disposable stream output to local Bronze only; PF-103 adds optional manual Dagster orchestration and run metadata; PF-104 adds optional local Prometheus and Grafana engineering observability over `stream_runs`. The public browser remains static and the committed public snapshot is unchanged.

For reproducible local engine comparisons, follow the [benchmark runbook](docs/runbooks/benchmarks.md). PF-105 compares DuckDB, Polars, and optional Docker-isolated PySpark over the same deterministic fixture; benchmark artifacts remain disposable under .benchmarks/ and are separate from public data.

For PF-106 offline BigQuery portability evidence, follow the [BigQuery portability runbook](docs/runbooks/bigquery-portability.md). The local bundle is credential-free, remains offline, and is separate from public data.

For PF-107 Databricks Free Edition Delta/PySpark handoff evidence and the PF-108 manual-result comparison, follow the [Databricks Free Edition runbook](docs/runbooks/databricks-free-edition.md). The default workflow is credential-free and offline; cloud execution remains a separate manual handoff.
