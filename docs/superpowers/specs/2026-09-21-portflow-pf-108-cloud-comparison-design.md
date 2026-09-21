# PF-108 Databricks Cloud Comparison Design

**Status:** Implementation-ready
**Date:** 2026-09-21
**Parent slice:** PF-107 Databricks Free Edition Delta/PySpark handoff
**Scope decision:** Credential-free comparison of an operator-supplied cloud result

## Goal

Add a deterministic, repository-local comparison command that checks an
operator-supplied Databricks Gold export against the trusted PF-107 local
reference. The command must make comparison evidence easy to produce after an
explicit, time-limited workspace run while keeping the default PortFlow
workflow offline, credential-free, and free of cloud API calls.

## Intended outcome

An operator should be able to:

- generate and verify the PF-107 offline handoff;
- place one exported `overview_kpis` JSON result below the ignored PF-108
  comparison root;
- compare it with the PF-107 `expected-result.json` using the shared canonical
  KPI field and hash contract;
- receive a stable `match` or `mismatch` report with exact file hashes and
  bounded reason codes; and
- distinguish a supplied result from proof that PortFlow itself executed a
  Databricks workspace run.

PF-108 does not claim that a Databricks workspace was run in CI or in the
current development environment. The cloud run and export remain an explicit
operator handoff; this feature makes the resulting comparison reproducible and
auditable once that handoff exists.

## Approved decisions

- Keep all PF-108 code in `labs/portflow_databricks/`; do not add cloud
  clients, credentials, environment-variable inspection, or workspace API
  calls to the production package.
- Reuse PF-107 `verify_bundle` as the trust anchor for the local handoff. A
  comparison cannot use an unverified or tampered PF-107 result.
- Accept only a JSON list of `overview_kpis` row objects as the cloud export.
  The field set and canonicalization are exactly the existing PF-106
  `RESULT_FIELDS`, UTC timestamps are encoded with a trailing `Z`, and no
  wrapper object or extra fields are accepted.
- Require the cloud export and comparison report to live below the ignored
  `.databricks/pf108/` root. Cross-platform absolute paths, traversal,
  backslashes, links, junctions, and reparse points are rejected.
- Write a deterministic `comparison.json` report. A semantic mismatch is a
  valid report with `status: "mismatch"` and a non-zero CLI exit; malformed
  input is a bounded command failure and never emits raw exception text.
- Report `execution_mode: "manual_result_comparison"` and
  `cloud_execution: "result_supplied"`. These values describe the artifact
  handoff only; they must never be interpreted as automatic cloud execution.
- Leave `web/public/data`, the public manifest, default Compose services,
  streaming, orchestration, observability, benchmarks, and the PF-107 bundle
  contract unchanged.

## Non-goals

- No Databricks SDK, CLI, REST request, login flow, notebook upload, volume
  creation, table creation, cluster creation, or workspace cleanup command.
- No automatic lookup or validation of credentials, tokens, workspace hosts,
  catalog identifiers, or account configuration.
- No attempt to infer execution timing, cost, compute type, or workspace
  provenance from a JSON result file.
- No new public page, dashboard route, browser asset, Product Design artifact,
  or Open Design artifact.
- No changes to KPI definitions, fixture generation, PF-107 notebook code, or
  the local dbt/DuckDB reference implementation.

## Architecture

```text
PF-107 verified handoff
  manifest + expected-result.json
              |
              v
      PF-108 local comparator <---- operator-supplied cloud-result.json
              |
              v
      deterministic comparison.json
       match / mismatch / bounded error
```

The comparator has three explicit boundaries:

1. `verify_bundle` validates the PF-107 manifest, notebook, schema, fixture,
   and expected-result hash without running dbt or contacting Databricks.
2. The comparison reader parses the cloud result, decodes its two UTC
   timestamp fields, and reuses `labs.portflow_bigquery.canonical` to produce
   a canonical row list and `result_sha256`.
3. The report writer records only bounded metadata and hashes, then the
   verifier rechecks the declared cloud file and the PF-107 reference before
   accepting the report.

## Interfaces

Create `labs.portflow_databricks.comparison` with:

```python
@dataclass(frozen=True)
class ComparisonSpec:
    repository_root: Path
    handoff_manifest: Path
    cloud_result: Path
    output_path: Path


def compare_result(spec: ComparisonSpec) -> dict[str, object]: ...


def verify_comparison(path: Path, *, repository_root: Path) -> None: ...
```

`compare_result` validates the PF-107 handoff, records its PF-107-relative
manifest path, and reads both result files,
computes canonical hashes, writes `output_path`, verifies the generated report,
and returns the report dictionary. Equal row hashes produce `status: "match"`;
different canonical hashes or row counts produce `status: "mismatch"` and
`reason_code: "result_hash_mismatch"`.

The `labs.portflow_databricks` CLI adds:

```text
python -m labs.portflow_databricks compare \
  --handoff-manifest .databricks/pf107/manifest.json \
  --cloud-result .databricks/pf108/cloud-result.json \
  --output .databricks/pf108/comparison.json
```

`--cloud-result` defaults to `.databricks/pf108/cloud-result.json`, and
`--output` defaults to `.databricks/pf108/comparison.json`. The command returns
zero only for a valid matching report. A valid mismatch returns one and prints
only `databricks comparison mismatch: result_hash_mismatch`. Invalid input
returns one and prints `databricks comparison failed: <safe-reason-code>`.

## Comparison report contract

The successful report is versioned as:

```json
{
  "schema_version": 1,
  "task": "PF-108",
  "target": "databricks_free_edition",
  "execution_mode": "manual_result_comparison",
  "cloud_execution": "result_supplied",
  "reference": {
    "task": "PF-107",
    "manifest_path": "handoff/manifest.json",
    "manifest_sha256": "...",
    "result_rows": 1,
    "result_sha256": "..."
  },
  "cloud_result": {
    "path": "cloud-result.json",
    "sha256": "...",
    "result_rows": 1,
    "result_sha256": "..."
  },
  "comparison": {
    "status": "match",
    "reason_code": null,
    "verifier_version": "1"
  }
}
```

The report may use `status: "mismatch"` and
`reason_code: "result_hash_mismatch"`; it remains deterministic and records
the cloud hash for diagnosis. No row payloads, absolute paths, workspace URLs,
credentials, subprocess output, or exception text enter the report.

## Error behavior

Only these reason codes may cross the CLI or report boundary:

- `artifact_path_invalid`
- `handoff_invalid`
- `cloud_result_invalid`
- `result_hash_mismatch`
- `cloud_result_hash_mismatch`
- `comparison_invalid`

Malformed JSON, non-list results, missing fields, extra fields, invalid
timestamps, non-finite metrics, duplicate terminals, missing artifacts, and
tampered files are converted to the applicable stable code. Unexpected
exception text is never printed or serialized.

## Test and documentation contract

Tests must cover:

- deterministic matching reports and exact row/hash reuse;
- canonical mismatch reports and non-zero CLI behavior;
- malformed, extra-field, duplicate, timestamp, and non-finite cloud rows;
- Windows/POSIX traversal, absolute paths, links, junctions, and reparse
  points for cloud input and report output;
- tampered PF-107 handoff, tampered cloud result, and tampered comparison
  report verification;
- hostile exception attributes and engine failures not leaking paths or
  secrets through the CLI; and
- unchanged public snapshot bytes and no cloud/network client imports.

Update the PF-107 runbook with the manual export placement, comparison command,
report interpretation, and cleanup boundary. Update the README, CHANGELOG, and
backlog with PF-108's artifact-only scope and explicitly record that no real
Databricks execution was performed by the repository workflow.
