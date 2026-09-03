# ADR 0001: Static public product

## Status

Accepted

## Context

PortFlow must be publicly accessible without a cloud bill, payment card, continuously running developer machine, or misleading claim of live terminal data.

## Decision

PortFlow V1 is published as static HTML, CSS, JavaScript, and versioned data assets. It has no production API, database, message broker, or server process. A browser-side replay may animate timestamped historical events but must always identify them as simulated data.

## Consequences

- The public product remains available while the developer machine is off.
- Public writes, accounts, authentication, and genuine public live streaming are outside V1.
- Data is refreshed by publishing a new validated static snapshot.
- The built `web/dist` directory remains portable to another static host.
