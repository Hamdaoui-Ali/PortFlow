# PF-107 Databricks Free Edition handoff

PF-107 is an offline, credential-free engineering handoff. It packages the
deterministic PF-106 four-table Parquet fixture, the checked-in Databricks
source notebook, the shared schema, and the local dbt/DuckDB expected Gold
result. It does not contact Databricks, inspect credentials, upload a
notebook, create a volume, or claim that a cloud run occurred.

## Generate and verify locally

From the repository root, use the project virtual environment:

```powershell
$env:PATH = "$(Get-Location)\.venv\Scripts;$env:PATH"
python -m labs.portflow_databricks run
python -m labs.portflow_databricks verify --manifest .databricks/pf107/manifest.json
```

Both successful commands print one stable line:

```text
databricks handoff bundle verified
```

The ignored bundle contains:

```text
.databricks/pf107/
  manifest.json
  portflow_delta_lab.py
  schema.json
  expected-result.json
  input-fingerprint.json
  fixture/<four logical tables>/part-000000.parquet
```

Repeat `run` in a fresh ignored directory and compare the `notebook`,
`schema`, `fixture`, and `expected_result` sections of each manifest. The
hashes must be identical. `verify` checks the notebook contract, declared
file hashes, Parquet logical hash, and canonical expected-result hash without
running dbt again.

The manifest records:

```json
{
  "execution_mode": "offline_handoff",
  "cloud_execution": "not_run",
  "compute": "serverless",
  "storage": "unity_catalog_volume_and_delta_tables"
}
```

## Manual Databricks handoff

Only after local verification, an operator may import
`.databricks/pf107/portflow_delta_lab.py` into a Databricks workspace. Upload
the four fixture directories to a Unity Catalog Volume and use the resulting
`/Volumes/<catalog>/<schema>/<volume>` root for the `input_root` widget. Set
`catalog`, `schema`, and `table_prefix` to a disposable Unity Catalog target.

Select Serverless compute and keep the Delta destinations fully qualified.
The notebook uses DataFrame reads, `pyspark.sql.functions`, widgets, and Delta
`saveAsTable` writes. It intentionally does not use RDDs, SparkContext,
Python UDFs, DBFS paths, Maven packages, direct network clients, or arbitrary
file writes. Compare the resulting Gold rows with `expected-result.json` and
the manifest's `result_sha256`; this comparison is manual evidence, not part
of the default local command.

Databricks Free Edition has quotas and fair-use limits, is serverless-only,
and is intended for non-commercial use without an SLA. Treat the workspace
run as optional and time-limited; no billing account or credential is needed
for the default local workflow.

## PF-108 result comparison

PF-108 does not execute Databricks. It compares a result that an operator has
already exported from an explicitly authorized workspace run with the trusted
PF-107 local reference. The comparison command is local, credential-free, and
does not execute notebooks, contact a workspace, inspect credentials, or infer
cloud provenance from the JSON file.

Place only the exported `overview_kpis` row list at:

```text
.databricks/pf108/cloud-result.json
```

The file must be a JSON array using the PF-106 `overview_kpis` field contract,
with UTC timestamps ending in `Z`. Then run:

```powershell
python -m labs.portflow_databricks compare `
  --handoff-manifest .databricks/pf107/manifest.json `
  --cloud-result .databricks/pf108/cloud-result.json `
  --output .databricks/pf108/comparison.json
```

The command prints `databricks comparison matched` and returns zero when the
canonical row hash and row count match. A valid difference prints
`databricks comparison mismatch: result_hash_mismatch`, returns one, and still
writes deterministic evidence. Malformed input, a tampered PF-107 handoff, or
a path violation prints one bounded `databricks comparison failed:` reason.
The report records `cloud_execution: result_supplied`; that is supplied-result
evidence, not a claim that PortFlow automatically executed the cloud run.

## Cleanup

Remove only the disposable local bundle when finished:

```powershell
Remove-Item -LiteralPath .databricks -Recurse -Force
```

In a workspace, separately remove the uploaded Volume files and disposable
Delta tables according to the workspace's permissions. Never copy PF-107
artifacts into `web/public/data`.
