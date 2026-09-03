# Data Health Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a snapshot-wide `#data-health` route that explains PortFlow freshness, quality evidence, reconciliation, rejects, and pipeline status.

**Architecture:** Extend the existing static snapshot loader with an explicit optional quality dataset state. Derive all health meaning in a pure `healthPresentation.ts` module using an injected clock and render it through focused React components. Integrate the route through the existing `App`/`AppShell` patterns without changing the published snapshot contract or global filters.

**Tech Stack:** React, TypeScript, Zod, Vitest, Testing Library, Vite, CSS, GitHub Pages static JSON.

**Spec:** `docs/superpowers/specs/2026-09-04-data-health-interface-design.md`

## Global Constraints

- The page is read-only, snapshot-wide, and does not inherit terminal/date filters.
- The stale threshold is exactly 24 hours after `manifest.generated_at`; the exact boundary is healthy.
- The existing `quality.json` export is authoritative for pipeline status, layer counts, quarantine counts, and rejection reasons.
- The UI must not calculate new business metrics.
- Do not change `schemas/public-snapshot-v1.json`, the Python pipeline, or the quality export format.
- Status meaning must be communicated with visible text, not color alone.
- Run frontend tests, typecheck, production build with `VITE_BASE_PATH='/PortFlow/'`, Pages verification, and `git diff --check` before completion.

---

### Task 1: Add typed quality dataset loading

**Files:**
- Modify: `web/src/data/schema.ts`
- Modify: `web/src/data/loadSnapshot.ts`
- Test: `web/src/data/loadSnapshot.test.ts`

**Interfaces:**
- Produces `QualityV1`, `QualityDatasetState`, and `SnapshotV1.quality` for later tasks.
- `QualityV1` fields are `bronze_rows`, `silver_rows`, `quarantine_rows`, `reason_counts`, and `dbt_test_status: "PASS"`.
- `QualityDatasetState` is `{ status: "absent" | "ready" | "unavailable" | "malformed" | "empty"; data?: QualityV1 }`, using the same explicit state semantics as existing optional datasets.

- [ ] **Step 1: Write failing schema and loader tests**

Add a manifest fixture with `datasets.quality.path` and a quality payload:

```ts
const quality = {
  bronze_rows: 305,
  silver_rows: 305,
  quarantine_rows: 0,
  reason_counts: {},
  dbt_test_status: "PASS",
};
```

Add tests asserting that `loadSnapshot` returns `{ status: "ready", data: quality }`, and separate tests for a missing quality entry (`absent`), a rejected fetch (`unavailable`), invalid JSON/schema (`malformed`), and `[]` (`empty`). Update the full snapshot fixture to include `quality` in its returned shape.

- [ ] **Step 2: Run the focused tests and verify failure**

Run from `web`:

```powershell
npm test -- --run src/data/loadSnapshot.test.ts --pool=forks --maxWorkers=1
```

Expected: FAIL because the quality schema, state, and loader branch do not exist.

- [ ] **Step 3: Implement the minimal typed quality contract**

In `schema.ts`, add:

```ts
export const qualitySchema = z.object({
  bronze_rows: z.number().int().nonnegative(),
  silver_rows: z.number().int().nonnegative(),
  quarantine_rows: z.number().int().nonnegative(),
  reason_counts: z.record(z.string().min(1), z.number().int().nonnegative()),
  dbt_test_status: z.literal("PASS"),
}).strict();

export type QualityV1 = z.infer<typeof qualitySchema>;
export type QualityDatasetState =
  | { status: "absent" }
  | { status: "ready"; data: QualityV1 }
  | { status: "unavailable" }
  | { status: "malformed" }
  | { status: "empty" };
```

Add `quality?: QualityDatasetState` to `SnapshotV1`. In `loadSnapshot.ts`, load the manifest-declared quality path with the existing five-second optional timeout. Treat a successful empty array as `empty`; parse only the object above; never let optional quality failure reject the required overview snapshot.

- [ ] **Step 4: Run the focused tests and verify passage**

```powershell
npm test -- --run src/data/loadSnapshot.test.ts --pool=forks --maxWorkers=1
```

Expected: PASS, including existing equipment, incidents, replay, and overview tests.

- [ ] **Step 5: Commit**

```powershell
git add web/src/data/schema.ts web/src/data/loadSnapshot.ts web/src/data/loadSnapshot.test.ts
git commit -m "feat: load typed data health evidence"
```

### Task 2: Derive the deterministic health view model

**Files:**
- Create: `web/src/features/health/healthPresentation.ts`
- Create: `web/src/features/health/healthPresentation.test.ts`

**Interfaces:**
- Consumes `ManifestV1` and `QualityDatasetState` from `web/src/data/schema.ts`.
- Produces `deriveHealthViewModel(manifest, quality, now): HealthViewModel`.
- `HealthViewModel.status` is `"healthy" | "stale" | "invalid"`.
- `HealthViewModel` includes `message`, `generatedAt`, `snapshotAgeMs`, `staleAfterMs`, `pipelineStatus`, `counts`, `rejections`, `reconciliation`, and `rules`.

- [ ] **Step 1: Write failing pure-function tests**

Use fixed dates and assert exact outputs for:

```ts
const manifest = { generated_at: "2026-09-04T00:00:00Z", snapshot_id: "demo-v2" } as ManifestV1;
const quality = { status: "ready", data: {
  bronze_rows: 305, silver_rows: 305, quarantine_rows: 0,
  reason_counts: {}, dbt_test_status: "PASS",
} } as const;
```

Cover: healthy at `2026-09-05T00:00:00Z`, stale one millisecond later, zero age for an earlier clock, invalid layer counts, invalid reason totals, and each absent/unavailable/malformed/empty quality state. Assert that rejection rows are sorted by reason code and that zero rejects produce an explicit empty state.

- [ ] **Step 2: Run the focused test and verify failure**

```powershell
npm test -- --run src/features/health/healthPresentation.test.ts --pool=forks --maxWorkers=1
```

Expected: FAIL because the presentation module does not exist.

- [ ] **Step 3: Implement pure derivation**

Define `STALE_AFTER_MS = 24 * 60 * 60 * 1000`. Compute `snapshotAgeMs = Math.max(0, now.getTime() - Date.parse(manifest.generated_at))`. Reconcile `bronze_rows === silver_rows + quarantine_rows` and `Object.values(reason_counts).reduce(...) === quarantine_rows`. Return invalid with a stable explanation for the first failed condition; return stale only after all evidence checks pass. Format values in this module or in pure helpers so components receive display-ready strings and ISO values.

- [ ] **Step 4: Run the focused test and verify passage**

```powershell
npm test -- --run src/features/health/healthPresentation.test.ts --pool=forks --maxWorkers=1
```

Expected: PASS for all deterministic boundary and evidence cases.

- [ ] **Step 5: Commit**

```powershell
git add web/src/features/health/healthPresentation.ts web/src/features/health/healthPresentation.test.ts
git commit -m "feat: derive data health status"
```

### Task 3: Build the Data Health page and focused components

**Files:**
- Create: `web/src/features/health/DataHealthPage.tsx`
- Create: `web/src/features/health/HealthStatus.tsx`
- Create: `web/src/features/health/HealthKpiRail.tsx`
- Create: `web/src/features/health/HealthEvidence.tsx`
- Create: `web/src/features/health/DataHealthPage.test.tsx`

**Interfaces:**
- Consumes `SnapshotV1` and `SnapshotState`-compatible stale information from `App` plus `deriveHealthViewModel`.
- Produces a page with heading, visible status explanation, `<time>` metadata, KPI labels, semantic evidence sections, rejection table, and rules disclosure.

- [ ] **Step 1: Write failing component tests**

Render a healthy snapshot and assert:

```ts
expect(screen.getByRole("heading", { name: "Data Health" })).toBeInTheDocument();
expect(screen.getByText("Healthy")).toBeInTheDocument();
expect(screen.getByText("305")).toBeInTheDocument();
expect(screen.getByText("No rejected records")).toBeInTheDocument();
expect(screen.getByRole("table", { name: /rejection reasons/i })).toBeInTheDocument();
```

Add stale and invalid fixtures and assert their explanatory text, generated timestamp, threshold text, and pipeline status. Assert that `main` and the rejection table are not live regions.

- [ ] **Step 2: Run the focused test and verify failure**

```powershell
npm test -- --run src/features/health/DataHealthPage.test.tsx --pool=forks --maxWorkers=1
```

Expected: FAIL because the page/components do not exist.

- [ ] **Step 3: Implement the page composition**

Create small components with one responsibility. Use `deriveHealthViewModel` with `new Date()` supplied by the page. Render status text and icon together, five labeled KPI values, pipeline/reconciliation evidence, a captioned table with `Reason` and `Rejected records` headers, and a native `details` element containing “Stale after 24 hours” plus links to `/docs/design/PORTFLOW_UI_SPEC.md` and `https://github.com/Hamdaoui-Ali/PortFlow`. Use visible explanatory text for all invalid and missing-quality states.

- [ ] **Step 4: Run the focused test and verify passage**

```powershell
npm test -- --run src/features/health/DataHealthPage.test.tsx --pool=forks --maxWorkers=1
```

Expected: PASS for healthy, stale, invalid, and empty-rejection render states.

- [ ] **Step 5: Commit**

```powershell
git add web/src/features/health
git commit -m "feat: build data health page"
```

### Task 4: Integrate route, navigation, and responsive styling

**Files:**
- Modify: `web/src/app/App.tsx`
- Modify: `web/src/app/App.test.tsx`
- Modify: `web/src/styles.css`

**Interfaces:**
- Consumes `snapshot.quality` and the existing `SnapshotState` branches.
- Produces `#data-health` route selection, active navigation, and page layout that remains independent of global filters.

- [ ] **Step 1: Write failing route tests**

Add tests that set `window.location.hash = "#data-health"`, render a valid snapshot containing quality evidence, and assert the Data Health heading, active `Data Health` link, and no filter mismatch message. Add a failed reload with a cached snapshot and assert the stale notice remains above Data Health.

- [ ] **Step 2: Run the focused route tests and verify failure**

```powershell
npm test -- --run src/app/App.test.tsx --pool=forks --maxWorkers=1
```

Expected: FAIL because `AppRoute`/`readRoute` do not select Data Health and `AppContent` does not render it.

- [ ] **Step 3: Integrate the route and styles**

Add `"data-health"` to `AppRoute`, map `#data-health` in `readRoute`, import and render `DataHealthPage` before filter matching, and pass `snapshot.manifest` plus `snapshot.quality`. Add styles using existing variables, dividers, table rules, and one-column mobile stacking. Do not add a filter control or broad `aria-live` region.

- [ ] **Step 4: Run route tests and verify passage**

```powershell
npm test -- --run src/app/App.test.tsx --pool=forks --maxWorkers=1
```

Expected: PASS, including existing navigation, stale-cache, overview, equipment, incident, and replay assertions.

- [ ] **Step 5: Commit**

```powershell
git add web/src/app/App.tsx web/src/app/App.test.tsx web/src/styles.css
git commit -m "feat: integrate data health route"
```

### Task 5: Harden boundaries and advance the backlog

**Files:**
- Modify: `web/src/data/loadSnapshot.test.ts`
- Modify: `web/src/features/health/healthPresentation.test.ts`
- Modify: `web/src/features/health/DataHealthPage.test.tsx`
- Modify: `web/src/app/App.test.tsx`
- Modify: `docs/product/BACKLOG.md`

**Interfaces:**
- Consumes all PF-022 implementation units from Tasks 1–4.
- Produces regression coverage and the backlog transition to PF-023 only after verification passes.

- [ ] **Step 1: Add boundary assertions**

Cover the exact stale boundary, a future generated timestamp, negative quality numbers, a reason count larger than quarantine, optional quality timeout, quality failure while Overview still renders, direct Data Health navigation, and invalid-status text that does not rely on color.

- [ ] **Step 2: Run the full frontend suite**

From `web`:

```powershell
npm test -- --run --pool=forks --maxWorkers=1 --reporter=dot
```

Expected: all tests pass.

- [ ] **Step 3: Run typecheck, build, Pages verification, and diff check**

```powershell
npm run typecheck
$env:VITE_BASE_PATH='/PortFlow/'; npm run build
npm run verify:pages
git diff --check
```

Expected: all commands exit successfully and Pages verification confirms `/PortFlow/` asset/data paths.

- [ ] **Step 4: Advance the backlog**

Change `docs/product/BACKLOG.md` so Current next action says PF-022 is complete and the next task is PF-023. Add the implementation commit hashes to the completed checkpoints in the existing concise style.

- [ ] **Step 5: Commit documentation**

```powershell
git add docs/product/BACKLOG.md
git commit -m "docs: advance backlog after data health"
```

- [ ] **Step 6: Request final code review and verify the merged tree**

Review the full PF-022 commit range for contract drift, stale/invalid truthfulness, accessibility regressions, and missing tests. Then rerun the full verification commands from Step 3 against the final tree before claiming completion.
