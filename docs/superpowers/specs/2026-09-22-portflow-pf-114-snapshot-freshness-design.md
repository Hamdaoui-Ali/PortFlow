# PF-114: Global snapshot freshness

**Status:** Proposed; implementation is in progress on `codex/pf-114-snapshot-freshness`.

## Problem

The shared mobile header currently always says “Healthy snapshot,” even when the snapshot is older than the 24-hour limit already enforced by Data Health. Desktop users have no global freshness indicator, and the generated timestamp is only visible on selected content. This can make stale operational data look current.

## Goal

Show the loaded snapshot’s real health/freshness state and generated time in the shared application header on every route and viewport. Reuse the existing Data Health interpretation so users receive the same status wherever they are in the product.

## User experience

- While loading, show “Loading snapshot.”
- When no snapshot can be loaded, show “Snapshot unavailable.”
- When rendering a cached snapshot after a load failure, show “Showing last valid snapshot.”
- For a successfully loaded snapshot, show a clear text label for current, stale, or invalid health and the existing health explanation.
- When a manifest is available, show its `generated_at` value as a readable UTC time and preserve the exact value in the `<time datetime>` attribute.
- Keep “Simulated terminal operations data” visible. Use text as well as color/iconography to communicate state.
- Keep the status in one shared header location on both desktop and mobile; do not show conflicting duplicate status labels.

## Constraints and non-goals

- Reuse `deriveHealthViewModel` and its existing 24-hour stale threshold; do not create a second freshness rule.
- Do not change the public snapshot, schema, generation process, backend, API, or route list.
- Do not claim a snapshot is current when health is stale or invalid.
- Preserve cached-snapshot behavior and the current Data Health page behavior.
- This is a focused shell-level status enhancement, not a broader visual redesign.

## Acceptance checks

- A current snapshot is labeled current, while a snapshot more than 24 hours old is labeled stale.
- Invalid pipeline/quality state is not presented as healthy.
- Loading, unavailable, and cached-fallback states are represented without inventing a timestamp when no manifest exists.
- The timestamp is available as semantic `<time>` markup and visibly includes UTC.
- Freshness remains visible after navigating between product routes.
- Desktop and mobile layouts remain readable without horizontal overflow, and status meaning is not color-only.
- Existing frontend tests, typecheck, production build, and page verification pass.
