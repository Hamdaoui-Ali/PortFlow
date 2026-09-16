# Changelog

## PortFlow V1 - 2026-09-16

PortFlow V1 is published at `https://hamdaoui-ali.github.io/PortFlow/`. The merged `main` commit passed CI and
the GitHub Actions Pages workflow completed both its build and deploy jobs.

### Included in V1

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
- The public root, hashed assets, manifest, versioned datasets, and brand mark returned HTTP 200.
- The published overview displayed the simulated-data disclosure and 94.4% equipment availability.
- Public route checks passed for Overview, Equipment, Incidents, Live Demo, and Data Health.
- Reduced-motion emulation disabled live motion styles while the replay still entered its playing state.

### Known boundaries

- The public build is static and snapshot-based; generated events and replay are simulated.
- No production runtime backend, live commercial feed, public write API, authentication, or public database is included.
- The local API remains loopback-only and PostgreSQL remains disposable local/CI state.
- The committed `demo-v2` snapshot is stale relative to the evidence date.
- The repository's `main` branch protection rules remain a separate hardening follow-up; the Pages environment and
  deploy job are restricted to `main`.
