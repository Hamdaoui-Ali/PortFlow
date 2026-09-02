# ADR 0002: Versioned snapshot boundary

## Status

Accepted

## Context

The local data platform and public frontend need a small, stable interface that does not expose PostgreSQL, DuckDB, or implementation-specific tables to browsers.

## Decision

Gold-to-JSON export is the only interface between the data platform and public application. A versioned `manifest.json` identifies immutable datasets, generation time, source-period bounds, record counts, quality status, relative paths, and SHA-256 content hashes.

The frontend validates the manifest and every dataset at runtime. The deployment workflow publishes only after export, schema, data, and frontend checks pass.

## Consequences

- Pipeline internals can change without rewriting the frontend when the public contract remains stable.
- Breaking contract changes require a new schema version and explicit frontend support.
- Invalid or incomplete snapshots cannot replace the last valid public deployment.
- The frontend never connects directly to PostgreSQL or DuckDB.
