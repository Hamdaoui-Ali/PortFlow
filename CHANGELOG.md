# Changelog

## Unreleased - 2026-09-16

PortFlow remains unreleased while the expected GitHub Pages URL is being provisioned. The local PF-030 gate is green, but `https://hamdaoui-ali.github.io/PortFlow/` and its required assets/data paths currently return HTTP 404.

### Included in this candidate

- Static operations control-tower views for Overview, Equipment, Incidents, Live Demo, and Data Health.
- A deterministic local PostgreSQL, validation, reconciliation, and snapshot-export pipeline.
- Published `demo-v2` replay data with explicit simulated-data disclosure.
- Loopback-only local data workspace and deterministic navigation state.
- Accessibility and responsive hardening, including readable trend checkpoints at narrow widths, zero page-level overflow at 320px and 375px, and equipment-detail return focus.
- GitHub Pages base-path safety checks for `/PortFlow/`.
- A deterministic one-worker frontend verification setting after the prior two-worker mode reproduced nondeterministic focus/navigation failures under the review environment.

### Verification

- 69 Python tests passed.
- 189 frontend tests passed, including failure-state, trend-label, and equipment-focus coverage.
- Ruff, mypy, TypeScript, Pages-path verification, byte budgets, and three Lighthouse runs passed.

### Known boundaries

- The public build is static and snapshot-based; generated events and replay are simulated.
- No production runtime backend, live commercial feed, public write API, authentication, or public database is included.
- The local API remains loopback-only and PostgreSQL remains disposable local/CI state.
- The committed `demo-v2` snapshot is stale relative to the evidence date.
- PF-030 stays open until GitHub Pages returns HTTP 200 for the page, hashed assets, manifest, datasets, and brand mark.
