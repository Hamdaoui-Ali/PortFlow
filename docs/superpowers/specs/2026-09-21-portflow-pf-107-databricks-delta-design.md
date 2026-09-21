# PF-107 Databricks Free Edition Delta/PySpark Lab

**Status:** Draft for implementation
**Date:** 2026-09-21
**Parent slice:** PF-106 offline BigQuery portability evidence
**Scope decision:** Offline, import-ready Databricks Free Edition notebook and
deterministic Delta/PySpark handoff bundle

## Goal

Add a repository-local Databricks Free Edition lab that shows how the existing
PortFlow telemetry-shaped fixture can move through Bronze, Silver, and Gold
Delta tables with serverless-compatible PySpark. The default repository
workflow remains offline and credential-free; a contributor may import the
committed notebook and upload the generated fixture to a Unity Catalog volume
for an explicit manual run in a Free Edition workspace.

## Intended outcome

The repository owner should be able to answer:

- Which notebook can be imported into Databricks Free Edition?
- Which input files, table names, and Unity Catalog volume path does it expect?
- Does the notebook use the serverless-safe DataFrame and Delta APIs rather
  than RDDs, DBFS mounts, or custom compute assumptions?
- Does the deterministic local fixture have the same expected Gold KPI result
  as the existing PortFlow contract?
- Which parts have been verified locally, and which parts still require an
  explicitly authorized Databricks workspace run?

The result is a reproducible handoff artifact, not a claim that Databricks has
executed the notebook or that Free Edition quotas are a production capacity.

## Approved decisions

- Keep all PF-107 orchestration code in a repository-only
  `labs/portflow_databricks/` package; do not add it to `src/portflow/` or the
  production wheel.
- Commit one Databricks source notebook at
  `labs/portflow_databricks/notebooks/portflow_delta_lab.py` using Databricks
  `# COMMAND ----------` cell separators and Python source format.
- Use the existing four-table PF-106 deterministic fixture as the input
  contract: `telemetry_events`, `container_movements`, `incidents`, and
  `alarms`.
- Generate only disposable local artifacts below `.databricks/pf107/`; keep
  them ignored and never copy them into `web/public/data`.
- Reuse the existing PF-106 fixture, schema, and local dbt/DuckDB reference
  contracts where their interfaces are stable instead of duplicating business
  logic.
- Make the notebook parameterized with Databricks widgets for the input volume
  path, catalog, schema, and table prefix. Defaults must be visibly safe demo
  values and must not contain credentials or a real workspace URL.
- Read Parquet from a Unity Catalog volume path, write explicit Bronze and
  Silver Delta tables, then write the existing `overview_kpis` field contract
  to a Gold Delta table.
- Use Spark DataFrame functions only for notebook transformations. Do not use
  RDD APIs, `SparkContext`, Python UDFs, DBFS mounts, Maven coordinates, or
  unrestricted network access.
- Use `saveAsTable` with fully qualified names for Delta outputs. The notebook
  must not write to arbitrary local paths or mutate the repository.
- Mark local artifacts with `execution_mode: "offline_handoff"` and
  `cloud_execution: "not_run"`. No Databricks client, token, credential
  environment variable, or workspace API may be inspected by the local CLI.
- Record the notebook, schema, fixture, and expected-result hashes in a
  versioned manifest. Failure output uses bounded reason codes and never raw
  subprocess or exception text.
- Document current Free Edition constraints: serverless-only compute, limited
  usage/fair-use quotas, Unity Catalog volume input, and no production/SLA
  claim. The runbook must direct users to stop using the workspace when the
  experiment is complete.
- Keep the public snapshot, default Docker Compose services, streaming,
  orchestration, observability, benchmark behavior, and web UI unchanged.

## Non-goals

- No Databricks workspace creation, login, REST API, SDK, CLI, or remote Git
  operation in CI or the default CLI.
- No committed Databricks credentials, workspace host, catalog identifiers
  tied to a personal account, or cloud execution result.
- No claim that the notebook has run in a Free Edition workspace unless a
  future explicitly authorized workflow records that evidence separately.
- No Delta Lake dependency in the production Python environment and no local
  emulation that pretends Parquet is Delta.
- No automatic notebook upload, table creation, volume creation, dashboard
  creation, or account-level configuration.
- No new public page, dashboard route, browser asset, or Product Design/Open
  Design artifact; this is an engineering lab and runbook only.
- No redesign of the existing KPI definitions or the known single-terminal
  incident association.

## Architecture

```text
PF-106 four-table Parquet fixture
                |
                v
   local run/verify contract checker
        /          |          \
       v           v           v
  source notebook  schema   expected Gold result
       |           |           |
       +-----------+-----------+
                   v
       versioned offline-handoff manifest
                   |
                   v
   optional manual Databricks Free Edition run
       Volume -> Bronze Delta -> Silver Delta -> Gold Delta
```

The local lab owns fixture preparation, notebook contract validation, expected
result generation, manifest writing, and manifest verification. The notebook
owns the cloud-side Spark/Delta execution path. These boundaries are
deliberate: local CI can prove the artifact is safe and internally consistent
without claiming that a remote workspace executed it.

### Repository package boundary

The package is invoked from the repository root:

```text
python -m labs.portflow_databricks run
python -m labs.portflow_databricks verify --manifest .databricks/pf107/manifest.json
```

`run` generates the PF-106-compatible fixture under the ignored PF-107 root,
copies the committed notebook and schema into the bundle, runs the existing
local dbt/DuckDB reference, and writes a bounded manifest. `verify` validates
the manifest, exact file hashes, notebook contract, fixture hash, and expected
result hash without modifying or contacting external systems.

### Notebook contract

The committed source notebook has these logical cells:

1. **Parameters:** create four widgets and read `input_root`, `catalog`,
   `schema`, and `table_prefix`.
2. **Bronze:** read each input Parquet table and write
   `<catalog>.<schema>.<prefix>_bronze_<table>` as Delta.
3. **Silver:** select and cast explicit columns for each input table and write
   `<catalog>.<schema>.<prefix>_silver_<table>` as Delta.
4. **Gold:** reproduce the existing KPI semantics with DataFrame expressions,
   including availability, utilization, throughput, dwell, MTTR, MTBF, active
   incidents, and critical alarms.
5. **Publish:** write the explicit `overview_kpis` projection to
   `<catalog>.<schema>.<prefix>_gold_overview_kpis` as Delta and display rows
   ordered by `terminal_id`.
6. **SQL handoff:** include a small Databricks SQL query showing how to inspect
   the Gold table without changing it.

The notebook must use only APIs supported by current serverless documentation:
DataFrame reads/writes, `pyspark.sql.functions`, Delta table writes, widgets,
and fully qualified Unity Catalog names. A static validator rejects forbidden
patterns even if they appear in comments or string literals where they could
mislead a reviewer.

### Expected result contract

The expected result uses the exact PF-106 `overview_kpis` field order and
canonicalization rules:

```text
terminal_id, source_period_start, source_period_end,
available_intervals, scheduled_intervals, active_intervals,
available_time_minutes, resolved_incident_count, repair_minutes,
qualifying_failure_count, operating_hours, throughput,
average_dwell_minutes, availability, utilization, mttr_minutes,
mtbf_hours, active_incidents, critical_alarms
```

The local expected result is read from the existing dbt/DuckDB Gold reference
over the same generated fixture. PF-107 does not run the notebook locally or
pretend that the expected result is a Databricks execution result. A future
authenticated workflow may compare a downloaded Gold result against this
hash.

## Artifact and manifest contract

Generated files live below the ignored `.databricks/pf107/` directory:

```text
.databricks/pf107/
  manifest.json
  portflow_delta_lab.py
  schema.json
  expected-result.json
  input-fingerprint.json
  fixture/
    telemetry_events/part-000000.parquet
    container_movements/part-000000.parquet
    incidents/part-000000.parquet
    alarms/part-000000.parquet
```

The successful manifest is versioned as:

```json
{
  "schema_version": 1,
  "task": "PF-107",
  "target": "databricks_free_edition",
  "execution_mode": "offline_handoff",
  "cloud_execution": "not_run",
  "compute": "serverless",
  "storage": "unity_catalog_volume_and_delta_tables",
  "notebook": {"path": "portflow_delta_lab.py", "sha256": "..."},
  "schema": {"path": "schema.json", "sha256": "..."},
  "fixture": {"tables": 4, "rows": {}, "sha256": "..."},
  "expected_result": {
    "path": "expected-result.json",
    "rows": 1,
    "sha256": "...",
    "result_sha256": "..."
  },
  "verification": {
    "status": "ok",
    "reason_code": null,
    "verifier_version": "1"
  }
}
```

The exact manifest schema is enforced in tests. Paths are relative artifact
names only. No absolute paths, raw environment dumps, workspace URLs,
credentials, or unbounded row payloads may enter a manifest.

## Safety and failure behavior

- The local CLI rejects output, manifest, and declared artifact paths that
  escape `.databricks/pf107/`, including POSIX and Windows traversal syntax,
  symlinks, junctions, and reparse points.
- The notebook validator rejects unrendered placeholders, missing required
  cells, wildcard projections, RDD/SparkContext/UDF/DBFS patterns, non-Delta
  output writes, and unqualified table names.
- A missing or modified notebook, schema, fixture, or expected result produces
  a stable reason code and a non-zero `verify` exit.
- A failed run cannot be reported as a successful handoff manifest.
- The local CLI catches expected file, JSON, validation, DuckDB, and Polars
  failures and prints only a bounded reason code.
- Verification does not modify `web/public/data`, the default `data/` tree,
  Docker Compose state, or existing PF-106 artifacts.

## Testing and verification

Before PF-107 is complete:

- unit tests cover notebook contract validation, explicit Delta table names,
  forbidden serverless-incompatible patterns, deterministic fixture reuse,
  expected-result canonicalization, path containment, manifest validation, and
  bounded failure reasons;
- an integration test runs the local CLI, verifies the bundle, and confirms
  repeat-run hashes are identical;
- tamper tests modify the notebook, schema, fixture, and expected result
  separately and assert the correct reason code;
- tests prove the bundle is ignored and the public snapshot remains unchanged;
- Ruff, mypy for the lab package, focused PF-107 tests, and the full existing
  Python suite pass; and
- the browser suite is unchanged because PF-107 has no UI surface.

## Documentation and repository boundaries

- `docs/runbooks/databricks-free-edition.md` explains local generation,
  verification, notebook import, volume upload, serverless execution, result
  comparison, quota/cost boundaries, and cleanup.
- `.gitignore` ignores `.databricks/` and generated PF-107 artifacts.
- `README.md` and `CHANGELOG.md` link to the runbook and state that the default
  workflow does not contact Databricks.
- The PF-107 entry in `docs/product/BACKLOG.md` is marked complete only after
  the design, implementation, tests, runbook, and verification evidence are
  committed; the next action becomes PF-108.

## References

- [Databricks Free Edition limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)
- [Serverless compute limitations](https://docs.databricks.com/aws/en/compute/serverless/limitations)
- [Git Folder Serverless](https://docs.databricks.com/aws/en/compute/serverless/git-folder-serverless)
- [Work with files in Unity Catalog volumes](https://docs.databricks.com/aws/en/volumes/volume-files)
- [What are workspace files?](https://docs.databricks.com/aws/en/files/workspace)
- [Import and export Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/notebook-export-import)

## Rollout and follow-up

PF-107 remains an explicit, disposable, credential-free local handoff until a
future operator chooses to import and run the notebook in a Databricks Free
Edition workspace. PF-108 may later add a separately authorized, time-limited
cloud comparison with credentials, cost guardrails, and a distinct workflow.
