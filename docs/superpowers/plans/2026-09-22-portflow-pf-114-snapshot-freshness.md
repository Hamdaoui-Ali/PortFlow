# PF-114: Global snapshot freshness implementation plan

**Goal:** Replace the misleading mobile-only “Healthy snapshot” label with an accurate shared-header freshness/status summary.

**Architecture:** `App` derives the header view model from its existing `SnapshotState`. Ready snapshots use `deriveHealthViewModel`; loading, unavailable, and cached-fallback states map from existing transitions. `AppShell` presents the status and manifest time across responsive layouts.

**Tech Stack:** React, TypeScript, Lucide icons, CSS, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-22-portflow-pf-114-snapshot-freshness-design.md`

## Global constraints

- `deriveHealthViewModel` remains the only freshness/quality authority; do not change its 24-hour threshold.
- Do not alter public data, schemas, generation, backend APIs, routes, dependencies, or existing Data Health behavior.
- Keep simulated-data disclosure visible, status text independent of color, and timestamp in semantic UTC `<time>` markup.
- All code edits stay in this feature worktree; preserve unrelated user files.
- Create focused commits and a PR; do not merge. Stop for user review/merge before another spec.

## Review focus

- No snapshot means no invented generated timestamp.
- Cached fallback must not be called current or healthy.
- Stale and invalid ready snapshots must use the existing health model’s visible state/message.
- UTC formatting must not shift the time and must include an explicit UTC label.
- Responsive status remains readable on narrow screens; no duplicate or contradictory claim.

---

### Task 1: Show truthful freshness in the shared header

**Files:** Modify `web/src/app/App.tsx`, `web/src/app/AppShell.tsx`, `web/src/app/App.test.tsx`, and `web/src/styles.css`.

**Interfaces:** Consume existing `SnapshotState`, `SnapshotV1`, and `deriveHealthViewModel`; pass a small typed view model from `App` to `AppShell`.

**Steps:**

1. Add an App test first for stale ready data under a deterministic clock, the exact 24-hour boundary if supported, accessible UTC timestamp, consistent status after route navigation, and loading without a timestamp. Run `web/src/app/App.test.tsx`; confirm it fails on the current hardcoded mobile-only “Healthy snapshot” and absent shared status.
2. Map loading and no-cache error explicitly; map cached fallback to “Showing last valid snapshot”; derive ready snapshot status/message through `deriveHealthViewModel` and map healthy/stale/invalid to explicit text labels.
3. Pass the status view model into `AppShell`, replace the hardcoded badge, and show one status with readable UTC generation time in the shared title region for desktop and mobile. Color/icons are supplemental only.
4. Run focused and full frontend tests, `npm run typecheck`, `npm run build`, and `npm run verify:pages` from `web/`. Check that generated public data/schema are unchanged; record exact results in the SDD ledger.

**Expected:** Tests, typecheck, build, and page verification pass; only the four implementation files and this spec/plan change; public snapshot/schema stay unchanged.
