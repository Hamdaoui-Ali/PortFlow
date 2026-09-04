# Responsive and Accessibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Overview, Equipment, Incidents, Live Demo, and Data Health keyboard-usable and responsive at narrow widths, with automated axe checks and a manual keyboard checklist.

**Architecture:** Keep accessibility behavior in the existing AppShell and feature components. Add one small `axe-core` scan helper and a Vitest-discovered `web/e2e/accessibility.spec.ts` suite that renders the real App with deterministic data. Apply only targeted semantic, focus, contrast, touch-target, overflow, and reduced-motion fixes; do not add a browser runner or redesign the product.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, jsdom, axe-core, Vite, CSS, GitHub Pages static deployment.

**Spec:** `docs/superpowers/specs/2026-09-04-responsive-accessibility-design.md`

## Global Constraints

- The work preserves the existing PortFlow visual system, native controls, table semantics, URL/history behavior, static data boundary, and feature boundaries.
- Add a minimal `axe-core`-based check to the existing Vitest/jsdom and Testing Library environment.
- The automated check must report zero axe violations for Overview, Equipment, Incidents, Live Demo, and Data Health.
- No page-level horizontal scroll at 320px or 375px.
- Interactive controls retain at least 44px touch targets.
- Status meaning is visible as text and does not depend on color alone.
- Reduced-motion users receive the same logical state and content without relying on animation.
- Do not add a browser E2E framework, new data, metrics, routes, backend behavior, or snapshot/pipeline changes.
- PF-024 end-to-end data reconciliation remains out of scope.

---

### Task 1: Add the axe test harness and route accessibility suite

**Files:**
- Modify: `web/package.json`
- Modify: `web/package-lock.json`
- Modify: `web/tsconfig.json`
- Create: `web/src/test/accessibility.ts`
- Create: `web/e2e/accessibility.spec.ts`

**Interfaces:**
- Produces `scanAccessibility(container: Element): Promise<AxeResults>` from `web/src/test/accessibility.ts`.
- The helper imports `axe-core` and runs against the supplied rendered container without mutating application code.
- The suite uses the existing `App` and `loadData` injection with a complete deterministic `SnapshotV1` fixture.

- [ ] **Step 1: Add the dependency and a failing suite**

Add `axe-core` to `devDependencies`. Add `e2e` to the TypeScript include list. Create `accessibility.spec.ts` with one test per route and assertions shaped like:

```ts
const results = await scanAccessibility(document.body);
expect(results.violations).toEqual([]);
```

Render routes by setting `window.location.hash` to `#overview`, `#equipment`, `#incidents`, `#live-demo`, and `#data-health` before rendering `App`. Use the existing snapshot contract fields, including ready equipment, incident, replay, and quality datasets, so every route renders its primary content.

- [ ] **Step 2: Install and run the suite to verify the expected baseline**

From `web`:

```powershell
npm install
npm test -- --run e2e/accessibility.spec.ts --pool=forks --maxWorkers=1
```

Expected: the suite runs and reports any current axe violations or test-harness errors. If the suite fails because a rule is genuinely violated, keep that failure as the RED signal for the next tasks; do not disable the rule globally.

- [ ] **Step 3: Implement the shared scan helper**

Implement:

```ts
import axe, { type AxeResults } from "axe-core";

export function scanAccessibility(container: Element): Promise<AxeResults> {
  return axe.run(container);
}
```

Use the helper in all five route tests. Keep the tests route-level and behavior-oriented; do not assert CSS class names as accessibility evidence.

- [ ] **Step 4: Run the harness suite and typecheck**

```powershell
npm test -- --run e2e/accessibility.spec.ts --pool=forks --maxWorkers=1
npm run typecheck
```

Expected: the helper compiles and the suite produces a concrete list of violations to fix in Tasks 2–4. If the baseline is already clean, retain the suite and add route-specific semantic assertions so it still fails when required semantics are removed.

- [ ] **Step 5: Commit**

```powershell
git add web/package.json web/package-lock.json web/tsconfig.json web/src/test/accessibility.ts web/e2e/accessibility.spec.ts
git commit -m "test: add route accessibility checks"
```

### Task 2: Harden shared shell semantics and focus behavior

**Files:**
- Modify: `web/src/app/AppShell.tsx`
- Modify: `web/src/app/App.tsx`
- Modify: `web/src/app/App.test.tsx`
- Modify: `web/src/styles.css`

**Interfaces:**
- Consumes the existing `AppRoute`, hash navigation, global filters, skip link, and `main#main-content`.
- Preserves `aria-current="page"` on the active desktop and mobile navigation links.
- Produces deterministic focus behavior: route content receives focus after hash navigation, while user focus is not stolen during ordinary control interaction.

- [ ] **Step 1: Write failing shell/focus tests**

Add tests that:

```ts
expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute("href", "#main-content");
expect(screen.getAllByRole("link", { name: "Data Health" })[0]).toHaveAttribute("aria-current", "page");
```

Simulate a hash route change and assert the route heading or main landmark receives focus. Assert that navigation, filter selects, and the skip link remain keyboard-focusable native elements.

- [ ] **Step 2: Run focused tests and verify failure**

```powershell
npm test -- --run src/app/App.test.tsx --pool=forks --maxWorkers=1
```

Expected: the new focus assertion fails before implementation, while existing App behavior remains green.

- [ ] **Step 3: Implement minimal shared-shell fixes**

Use a ref on `main#main-content` or the active route heading and a hash-change effect to focus the newly selected route only when navigation originated from a route link. Keep `tabIndex={-1}` on the focus target. Ensure both navigation variants expose the same link names and `aria-current` state. Extend the shared focus-visible selector to every interactive family used by the shell and avoid adding a broad live region.

- [ ] **Step 4: Verify focused behavior**

```powershell
npm test -- --run src/app/App.test.tsx --pool=forks --maxWorkers=1
npm test -- --run e2e/accessibility.spec.ts --pool=forks --maxWorkers=1
```

Expected: App tests and the current route accessibility suite pass for shared-shell rules; feature-specific violations remain for their tasks.

- [ ] **Step 5: Commit**

```powershell
git add web/src/app/AppShell.tsx web/src/app/App.tsx web/src/app/App.test.tsx web/src/styles.css
git commit -m "fix: harden shell accessibility"
```

### Task 3: Harden feature semantics, charts, and detail navigation

**Files:**
- Modify: `web/src/features/overview/AvailabilityCard.tsx`
- Modify: `web/src/features/overview/AvailabilityTrend.tsx`
- Modify: `web/src/features/overview/OverviewKpiRail.tsx`
- Modify: `web/src/features/equipment/EquipmentTable.tsx`
- Modify: `web/src/features/equipment/EquipmentDetail.tsx`
- Modify: `web/src/features/equipment/EquipmentPage.tsx`
- Modify: `web/src/features/incidents/IncidentTable.tsx`
- Modify: `web/src/features/incidents/IncidentDetail.tsx`
- Modify: `web/src/features/incidents/IncidentPage.tsx`
- Modify: `web/src/features/replay/ReplayControls.tsx`
- Modify: `web/src/features/replay/ReplayActivityFeed.tsx`
- Modify: `web/src/features/replay/LiveDemoPage.tsx`
- Modify: `web/src/features/health/HealthEvidence.tsx`
- Modify: `web/src/features/health/DataHealthPage.tsx`
- Test: existing feature test files plus `web/e2e/accessibility.spec.ts`

**Interfaces:**
- Consumes each feature’s existing typed data and URL/history state.
- Produces named controls, valid heading relationships, semantic tables, textual chart summaries, honest status regions, and focusable detail transitions without changing feature data behavior.

- [ ] **Step 1: Add failing route-specific semantic assertions**

Extend the accessibility suite and feature tests with concrete assertions:

```ts
expect(screen.getByRole("img", { name: /hourly availability trend/i })).toBeInTheDocument();
expect(screen.getByRole("table", { name: "Equipment fleet" })).toBeInTheDocument();
expect(screen.getByRole("table", { name: /incident/i })).toBeInTheDocument();
expect(screen.getByRole("button", { name: /pause replay|start replay/i })).toBeInTheDocument();
expect(screen.getByRole("table", { name: /rejection reasons/i })).toBeInTheDocument();
```

Add tests for keyboard detail selection/back behavior and for an explicit textual unavailable/empty state on every optional dataset. Add a chart-summary assertion that describes the rendered trend without requiring visual inspection.

- [ ] **Step 2: Run the focused feature and axe tests to verify failures**

```powershell
npm test -- --run src/features e2e/accessibility.spec.ts --pool=forks --maxWorkers=1
```

Expected: any remaining route-specific axe/semantic failures identify the exact feature boundary to correct.

- [ ] **Step 3: Implement minimal semantic and focus corrections**

Keep native `button`, `select`, `details`, `table`, `caption`, `th`, and `time` elements. Correct heading IDs/`aria-labelledby`, table captions and scopes, sortable-header `aria-sort`, chart summaries, control names/states, and status text. When a detail view opens, focus its heading; when the back action returns, restore focus to the originating list context. Keep replay status live only on the concise status element, never on the full activity feed. Do not claim data is available when its state is absent, malformed, empty, or unavailable.

- [ ] **Step 4: Run feature and axe tests**

```powershell
npm test -- --run src/features e2e/accessibility.spec.ts --pool=forks --maxWorkers=1
```

Expected: all feature tests and axe route scans pass with zero violations.

- [ ] **Step 5: Commit**

```powershell
git add web/src/features web/e2e/accessibility.spec.ts
git commit -m "fix: harden feature accessibility"
```

### Task 4: Complete responsive, contrast, touch-target, and motion behavior

**Files:**
- Modify: `web/src/styles.css`
- Modify: relevant feature tests and `web/e2e/accessibility.spec.ts`

**Interfaces:**
- Consumes existing component class names and route markup from Tasks 2–3.
- Produces layouts that remain within the viewport at 320px and 375px, bounded table scrolling, 44px interactive targets, visible focus, and reduced-motion equivalence.

- [ ] **Step 1: Add failing responsive assertions**

Add stylesheet/DOM assertions for:

```ts
expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(document.documentElement.clientWidth);
```

Run the rendered routes at 320px and 375px viewport widths. Assert that table overflow is confined to `.equipment-table-overflow`, `.table-scroll-region`, or `.health-table-scroll`, while the page itself does not overflow. Assert all interactive controls have computed or declared minimum height of 44px where the existing CSS contract applies.

- [ ] **Step 2: Run responsive tests and identify failures**

```powershell
npm test -- --run e2e/accessibility.spec.ts --pool=forks --maxWorkers=1
```

Expected: any narrow-screen or target-size failures are reproducible before CSS fixes.

- [ ] **Step 3: Implement targeted responsive CSS**

At the existing `max-width: 899px` breakpoint, stack health/replay KPI rails and analytical grids where required. Keep tables as tables inside bounded overflow regions; hide only approved lower-priority columns already defined by the product layout. Ensure filter controls and mobile navigation remain usable at 320px. Use the existing `--border`, `--focus`, `--muted`, `--cobalt`, `--teal`, `--warning`, and `--danger` tokens. Keep focus outlines visible and extend the reduced-motion media query to every animated/transitioned surface affected by PF-023.

- [ ] **Step 4: Verify responsive and motion behavior**

```powershell
npm test -- --run e2e/accessibility.spec.ts --pool=forks --maxWorkers=1
npm run typecheck
$env:VITE_BASE_PATH='/PortFlow/'; npm run build
npm run verify:pages
git diff --check
```

Expected: axe, viewport assertions, typecheck, build, Pages verification, and diff check pass.

- [ ] **Step 5: Commit**

```powershell
git add web/src/styles.css web/e2e/accessibility.spec.ts web/src/features web/src/app
git commit -m "fix: complete responsive behavior"
```

### Task 5: Record the manual checklist and complete PF-023 verification

**Files:**
- Create: `docs/runbooks/accessibility-checklist.md`
- Modify: `docs/product/BACKLOG.md`

**Interfaces:**
- Consumes the verified UI and automated route suite from Tasks 1–4.
- Produces a repository checklist with pass/fail evidence fields and advances the backlog to PF-024 only after all gates pass.

- [ ] **Step 1: Write the manual checklist**

Create a concise checklist with rows for Overview, Equipment, Incidents, Live Demo, and Data Health. Include these exact checks: skip-link order, focus visibility on links/selects/buttons/details/table controls, detail-page focus return, 320px and 375px page overflow, table-contained overflow, and reduced-motion state equivalence. Add columns for viewport/browser, observation, result, and date.

- [ ] **Step 2: Run all automated verification**

From `web`:

```powershell
npm test -- --run --pool=forks --maxWorkers=1 --reporter=dot
npm run typecheck
$env:VITE_BASE_PATH='/PortFlow/'; npm run build
npm run verify:pages
git diff --check
```

Expected: all commands exit successfully, with zero axe violations and no test failures.

- [ ] **Step 3: Complete the manual checklist against the rendered app**

Use the local rendered app at 320px and 375px plus keyboard-only interaction. Record concrete observations for every checklist row. Any blocker must be fixed in the owning feature task before continuing.

- [ ] **Step 4: Advance the backlog**

Update `docs/product/BACKLOG.md` so Current next action names PF-024, and add the PF-023 implementation commit hashes to the completed checkpoint in the existing concise style.

- [ ] **Step 5: Commit the checklist and backlog separately**

```powershell
git add docs/runbooks/accessibility-checklist.md
git commit -m "docs: add accessibility checklist"
git add docs/product/BACKLOG.md
git commit -m "docs: advance backlog after accessibility"
```

- [ ] **Step 6: Request final code review and verify the merged tree**

Review the full PF-023 commit range for semantic regressions, inaccessible states, keyboard focus theft, viewport overflow, dependency scope, and test quality. Rerun the full verification commands against the final tree before claiming completion.
