# PortFlow Local Data Workspace and Navigation Reliability

**Status:** Approved for implementation planning  
**Date:** 2026-09-11  
**Scope:** Local development workflow and the existing static React application

## Goal

Make the application dependable when changing sections and make the existing PostgreSQL pipeline usable by a developer or operator. A user should be able to start the local database, seed or import operational records, regenerate the public snapshot, and see the result in PortFlow without editing source files or guessing where database work belongs.

The public product remains a static snapshot. The browser must never connect directly to PostgreSQL, DuckDB, or a production database. Database access is provided only by a loopback-only local API used during development.

## Existing product constraints

- Keep the approved navigation labels and visual system in `docs/design/PORTFLOW_UI_SPEC.md`.
- Keep the five existing destinations: `Overview`, `Equipment`, `Incidents`, `Live Demo`, and `Data Health`.
- Do not add a public account flow, public write API, authentication system, or hosted database.
- Reuse the existing `TABLE_SPECS`, migration runner, seed routine, validation rules, and local pipeline instead of creating a second data model.
- The local workspace is an operational tool, not a new visual concept. It belongs inside `Data Health` so the existing navigation contract remains intact.

## Navigation decision

The current route pages are dynamically imported. On a cold load, the shell renders `Loading selected view` while the selected page chunk is fetched. That loading state is easy to interpret as a stuck menu, particularly on the first visit to a section. The first implementation will eagerly import the five small route pages and remove the route-level `Suspense` boundary. Snapshot loading remains asynchronous and keeps its existing loading, stale-cache, and error states.

This trades a small increase in the initial JavaScript bundle for deterministic section changes. The build budget is the guardrail; if the resulting bundle exceeds the existing budget, the fallback design is to retain lazy imports but preload every route module when the shell mounts and keep an explicit error boundary for failed chunks. Either implementation must satisfy the same acceptance criterion: clicking a navigation item renders the selected page without replacing the main content with an indefinite loading state.

The global filter writer in `AppShell` will also preserve `window.location.hash` when it updates query parameters. This prevents changing terminal or time range from silently removing the current route from the URL. A regression test will cover filter changes from both a section route and the overview route.

## Local architecture

```text
Data Health workspace
        |
        | fetch /api/* (local development only)
        v
127.0.0.1:8000  --  portflow.local_api
        |
        +--> migrations / seed / allow-listed imports --> PostgreSQL :5433
        |
        +--> run_local_pipeline --> web/public/data/*.json
                                      |
                                      v
                                  static React snapshot
```

### Local API

Add a small standard-library HTTP service so the project does not acquire a new web framework just to expose local tooling:

- `src/portflow/local_api.py` owns the loopback server, request routing, JSON encoding, bounded request bodies, and sanitized error responses.
- `src/portflow/local_data.py` owns the import contract and database operations. It consumes the existing table allowlist and schema rules, uses parameterized values, and never interpolates an arbitrary table or column name.
- `scripts/run_local_api.py` is the documented launcher.
- `web/vite.config.ts` proxies `/api` to `http://127.0.0.1:8000` during `npm run dev`.

The service binds to `127.0.0.1` only. It accepts browser requests from local development origins (`localhost` and `127.0.0.1` on the Vite port) and does not allow hosted origins. It never returns the database URL or credentials. A request body is capped, malformed JSON is rejected, and SQL identifiers come only from a fixed allowlist.

The endpoints are:

- `GET /api/status` — database and local pipeline readiness, without secrets.
- `GET /api/schema` — the supported tables, columns, types, and short field guidance derived from the same allowlist used by ingestion.
- `POST /api/seed` — apply migrations and run the existing deterministic demo seed.
- `POST /api/import` — accept `{ "table": "...", "records": [...] }`; validate required fields, types, references, ranges, and timestamps, then insert or update by the table primary key in one transaction.
- `POST /api/refresh` — run the existing local pipeline and regenerate `web/public/data`; reject a concurrent refresh with `409`.

Imports are deliberately JSON in the first slice. The Data Health UI provides a table selector, schema guidance, an example payload, a JSON editor/file picker, row-level validation errors, and inserted/updated counts. This supports all seven existing source tables without inventing seven unrelated forms. CSV and richer per-entity forms remain follow-up work.

Database writes happen in dependency order (`terminals`, then `equipment`, then dependent operational tables). A failed validation or database constraint rolls back the entire import. The response identifies the table, row index, field, and reason so a user can correct the payload. Seed and import do not silently regenerate the snapshot; the UI exposes a separate `Refresh snapshot` action, making the database-to-snapshot boundary visible.

### Frontend workspace

Add `web/src/data/localApi.ts` as a small typed client and `web/src/features/health/LocalDataWorkspace.tsx` inside the existing `DataHealthPage`. It must render independently of snapshot loading:

- `Checking local connection` while `/api/status` is requested.
- `Local database connected` with seed/import/refresh actions when ready.
- `Local API unavailable` with the exact local startup command when the public static app or a developer who has not started the service uses the page.
- Busy, success, validation-error, database-error, and refresh-required states with `role="status"` or `role="alert"` as appropriate.

The workspace must use the existing typography, colors, borders, spacing, focus treatment, and minimum target sizes. It must not add a sidebar item, change mobile bottom navigation, or block the health metrics while the local status request is pending. After a successful refresh, the client reloads the snapshot so the existing `loadSnapshot` path remains the single source of truth for displayed operational data.

## Data flow and failure behavior

1. The developer starts PostgreSQL with `docker compose up -d --wait postgres` and launches the local API.
2. The workspace reads status and schema. It remains usable when either PostgreSQL or the API is unavailable.
3. Seed or import validates and writes to PostgreSQL transactionally.
4. Refresh runs the existing Bronze/Silver/Gold pipeline and writes the versioned JSON snapshot.
5. The frontend reloads and renders the refreshed snapshot through the existing cache and stale-data behavior.

No error path should leave a disabled-looking page without an explanation. Network errors, a stopped database, invalid records, concurrent refreshes, and pipeline failures must all surface a concise recovery action. The API must log server-side details but return safe messages to the browser.

## Verification targets

Frontend tests will cover eager route rendering, menu navigation, filter/hash preservation, local API client errors, workspace states, successful seed/import/refresh flows, and the mobile target-size rule. Backend unit tests will cover allowlist enforcement, payload validation, dependency ordering, transaction rollback behavior through the data-service boundary, request-size/origin restrictions, and sanitized responses. Existing PostgreSQL integration tests will cover real imports, idempotency, constraints, and refreshed snapshot output when Docker is available.

The implementation is accepted only when:

- a cold click on every menu item reaches its page reliably;
- changing a global filter does not remove the active route from the URL;
- a local user can see connection status, seed demo data, import a supported JSON payload, and refresh the snapshot from `Data Health`;
- the public/static app clearly explains why local database tools are unavailable there;
- existing type, lint, unit, build, accessibility, and data-pipeline checks remain green;
- the runbook documents the complete local workflow and the current Docker limitation is reported honestly if verification cannot start PostgreSQL.

## Non-goals

This change does not create a hosted backend, expose PostgreSQL outside localhost, add authentication, replace the static deployment model, redesign the PortFlow visual language, or add arbitrary SQL/query access from the browser.
