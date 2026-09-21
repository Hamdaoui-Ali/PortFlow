# Local development and data workspace

This runbook explains how to start PortFlow's local PostgreSQL pipeline, connect the Data Health page to it, import operational records, and regenerate the static snapshot.

## Architecture boundary

- The public PortFlow site is static HTML, CSS, JavaScript, and versioned JSON.
- PostgreSQL is disposable local development state and listens on host port `5433`.
- The local API listens only on `127.0.0.1:8000`. It is used by the Vite development server through `/api` proxy requests.
- The browser never connects directly to PostgreSQL, DuckDB, or a hosted database.

The hosted/static site intentionally shows **Local API unavailable**. That is expected: the published site has no database connection or write service.

## Prerequisites

- Python `3.12` or newer.
- Docker Desktop running with its Linux engine enabled.
- Node.js and npm.

## First-time setup

From PowerShell, create the existing project environment and install the locked frontend dependencies:

```powershell
Set-Location C:/Users/aliha/PortFlow
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
Set-Location web
npm install
Set-Location ..
```

The repository's `.env.example` records the non-secret local defaults. Generate a disposable password in the terminal that starts PostgreSQL and the API; do not commit or print it:

```powershell
Set-Location C:/Users/aliha/PortFlow
$env:PORTFLOW_POSTGRES_PASSWORD = [Guid]::NewGuid().ToString("N")
$env:PORTFLOW_DATABASE_URL = "postgresql://portflow:$($env:PORTFLOW_POSTGRES_PASSWORD)@localhost:5433/portflow"
$env:PORTFLOW_LOCAL_API_PORT = "8000"
```

## Start the local workflow

Use two terminals. In terminal 1, start PostgreSQL and keep the API running:

```powershell
Set-Location C:/Users/aliha/PortFlow
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
if (-not $env:PORTFLOW_POSTGRES_PASSWORD) {
    $env:PORTFLOW_POSTGRES_PASSWORD = [Guid]::NewGuid().ToString("N")
}
if (-not $env:PORTFLOW_DATABASE_URL) {
    $env:PORTFLOW_DATABASE_URL = "postgresql://portflow:$($env:PORTFLOW_POSTGRES_PASSWORD)@localhost:5433/portflow"
}
docker compose up -d --wait postgres
./.venv/Scripts/python.exe scripts/run_local_api.py
```

In terminal 2, start the Vite development server:

```powershell
Set-Location C:/Users/aliha/PortFlow/web
npm install
npm run dev
```

Open the local Vite address printed by the terminal and choose **Data Health** from the menu. The health metrics render independently of the local API status check.

## Seed, import, and refresh

On **Data Health**:

1. Choose **Seed demo data** to apply migrations and load the deterministic fixture.
2. Or choose a table, paste JSON into **JSON records**, and choose **Validate and import**.
3. After a successful import, choose **Refresh snapshot** to run the existing PostgreSQL-to-public-data pipeline.

Imports are allow-listed full-row upserts. The selected record's primary key determines whether it is inserted or updated. Unknown fields, missing fields, invalid types, invalid ranges, duplicate keys, missing foreign keys, and database constraint failures are rejected; a failed batch does not leave a partial write.

The seven available tables and their required fields are:

| Table | Required fields and references |
| --- | --- |
| `terminals` | `terminal_id`, `name`, `timezone_name`, `created_at`, `updated_at` |
| `equipment` | `equipment_id`, `terminal_id` (existing terminal), `equipment_type`, `commissioning_date`, `created_at`, `updated_at` |
| `telemetry_events` | `event_id`, `schema_version`, `equipment_id` (existing equipment), `terminal_id` (existing terminal), `event_timestamp`, `ingestion_timestamp`, `state`, `available`, `load_percent`, `temperature_c`, `created_at`, `updated_at` |
| `alarms` | `alarm_id`, `equipment_id` (existing equipment), `severity`, `code`, `opened_at`, `cleared_at` (nullable), `created_at`, `updated_at` |
| `incidents` | `incident_id`, `equipment_id` (existing equipment), `severity`, `status`, `opened_at`, `resolved_at` (nullable), `root_cause`, `created_at`, `updated_at` |
| `maintenance_orders` | `maintenance_order_id`, `equipment_id` (existing equipment), `status`, `started_at`, `completed_at` (nullable), `created_at`, `updated_at` |
| `container_movements` | `movement_id`, `terminal_id` (existing terminal), `equipment_id` (existing equipment), `movement_type`, `container_ref`, `event_timestamp`, `created_at`, `updated_at` |

Use UTC ISO-8601 timestamps with a `Z` suffix. `updated_at` cannot be earlier than `created_at`. Nullable resolution fields must match their status: a resolved incident requires `resolved_at`, a completed maintenance order requires `completed_at`, and an open/unfinished record leaves its completion field `null`. Equipment and telemetry values must use the enum and range values defined by the schema.

This is a valid `incidents` import after the referenced equipment exists:

```json
[
  {
    "incident_id": "inc-000101",
    "equipment_id": "QC-001",
    "severity": "MAJOR",
    "status": "OPEN",
    "opened_at": "2026-09-02T12:00:00Z",
    "resolved_at": null,
    "root_cause": "Hydraulic leak",
    "created_at": "2026-09-02T12:00:00Z",
    "updated_at": "2026-09-02T12:00:00Z"
  }
]
```

The editor also accepts an object containing a `records` array. A successful import reports received, inserted, and updated counts. Validation errors identify the row and field that need correction.

## Stop and reset

Stop the API with `Ctrl+C`, then stop the disposable database when finished:

```powershell
Set-Location C:/Users/aliha/PortFlow
docker compose down
```

To remove the local database volume as well, use `docker compose down -v`. This permanently removes only the disposable PostgreSQL data created by Compose; the committed public snapshot is unchanged.

## Troubleshooting

- **Local API unavailable:** confirm terminal 1 is still running and that `PORTFLOW_DATABASE_URL` points to host port `5433`. The Data Health metrics remain available while the local tools are offline.
- **Docker cannot connect to its Linux engine:** open Docker Desktop, enable the Linux engine, and retry `docker compose up -d --wait postgres`.
- **Foreign-key validation error:** seed first, or import parent rows in order: `terminals`, then `equipment`, then dependent tables.
- **Snapshot did not change:** a refresh only publishes after the full pipeline succeeds. Check the API terminal for the server-side failure, correct the data, and retry.
