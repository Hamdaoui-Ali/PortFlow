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

For the opt-in Kafka-compatible telemetry path, follow the [local Redpanda streaming runbook](docs/runbooks/local-streaming.md). It writes disposable stream output to local Bronze only; the public browser remains static and the committed public snapshot is unchanged.
