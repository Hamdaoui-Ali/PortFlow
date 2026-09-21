# Offline BigQuery portability runbook

## Scope and artifact boundary

PF-106 creates a local, disposable SQL portability bundle under
`.portability/bigquery/`. The bundle is offline engineering evidence: it does
not modify `web/public/data`, does not update the public site, and is not public data.
The fixture is synthetic engineering data, not public product data.

Generated SQL is GoogleSQL-ready, but it was not sent to BigQuery. The local
manifest records `cloud_execution` as `not_run`; that value must remain
`not_run` for this offline workflow.

## Prerequisites

Use the repository's local Python environment. No Google Cloud credentials,
project, billing account, network access, or cloud command is required.
Credentials are neither required nor inspected by the local generator or
verifier.

## Generate and verify the local bundle

Run the local generator:

```text
python -m labs.portflow_bigquery run
```

Then verify the generated manifest and SQL bundle:

```text
python -m labs.portflow_bigquery verify --manifest .portability/bigquery/manifest.json
```

These commands produce and validate local evidence only. They do not execute
queries in BigQuery and do not require credentials.

## Inspect the manifest

Inspect `.portability/bigquery/manifest.json` to confirm the generated file
hashes and the offline execution boundary. Its `cloud_execution` field must be
`not_run`. The SQL uses GoogleSQL compatibility expressions including `COUNTIF`
and `TIMESTAMP_DIFF`.

## Future BigQuery dry-run handoff

The following is a future authenticated handoff template. It is deliberately
outside the default workflow and must not be run as part of PF-106's offline,
credential-free evidence:

```text
bq query --use_legacy_sql=false --dry_run --project_id=demo-project < .portability/bigquery/overview_kpis.sql
```

Before a future dry run, an authorized operator must provide credentials and a
permitted project. That handoff can validate parsing without executing the
query, but it does not change the PF-106 record that cloud execution is
`not_run`.

## Compatibility limitation

The current single-terminal incident association is preserved for compatibility.
This portability bundle does not introduce multi-terminal incident association
or change the existing model.

## Cleanup

Remove the disposable local bundle when it is no longer needed:

```text
Remove-Item .portability -Recurse -Force
```
