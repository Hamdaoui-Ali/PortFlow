# Equipment Exploration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build a static, accessible equipment fleet table with search, sorting, global terminal filtering, and URL-preserved detail routing.

**Architecture:** Extend the validated snapshot boundary with explicit equipment dataset status. Keep pure filtering, sorting, and URL parsing in feature-local helpers. Add an equipment page and detail view behind the existing hash navigation while preserving Overview recovery.

**Tech Stack:** React 19, TypeScript, Zod, Vitest, Testing Library, Lucide React, Vite.

**Spec:** docs/superpowers/specs/2026-09-03-equipment-exploration-design.md

## Global Constraints

- Keep the public product static and browser-only.
- Use only validated snapshot data; never invent missing values in the UI.
- Preserve the approved divider-led PortFlow visual system.
- Reuse global terminal and date-range filter state.
- Preserve loading, unavailable, malformed, empty, and stale recovery behavior.
- Do not add a client-side routing dependency.
- Keep all controls keyboard reachable and at least 44 px high.

## File map

- web/src/data/schema.ts: equipment schema and dataset-state types.
- web/src/data/loadSnapshot.ts and loadSnapshot.test.ts: optional equipment fetch and status tests.
- web/src/features/equipment/equipmentTable.ts and test: pure filtering and sorting.
- web/src/features/equipment/equipmentUrlState.ts and test: URL defaults and serialization.
- web/src/features/equipment/EquipmentTable.tsx and test: accessible fleet table.
- web/src/features/equipment/EquipmentDetail.tsx and test: selected-record detail.
- web/src/features/equipment/EquipmentPage.tsx and test: page states and interactions.
- web/src/app/App.tsx and App.test.tsx: hash route and recovery handoff.
- web/src/styles.css: table, detail, and responsive rules.
- docs/product/BACKLOG.md: next-action update after verification.

### Task 1: Extend the snapshot contract

**Files:** Modify web/src/data/schema.ts, web/src/data/loadSnapshot.ts, and web/src/data/loadSnapshot.test.ts.

**Interfaces:** Produce EquipmentRecordV1 with equipment_id, terminal_id, current_state, available, availability, utilization, downtime_minutes, alarm_count, mttr_minutes, and mtbf_hours. Produce EquipmentDatasetState as absent, ready with records, unavailable, malformed, or empty. Extend SnapshotV1 with equipment?: EquipmentDatasetState.

- [ ] Write failing loader tests for valid data, missing manifest entry, failed fetch, malformed shape, and an empty array.

    expect(snapshot.equipment).toEqual({ status: "ready", records: equipment });
    expect(failedSnapshot.equipment).toEqual({ status: "unavailable" });
    expect(emptySnapshot.equipment).toEqual({ status: "empty" });

- [ ] Run RED:
    npx vitest run --pool=forks --maxWorkers=1 src/data/loadSnapshot.test.ts --reporter=dot
    Expected: failure because the equipment contract does not exist.

- [ ] Implement a strict equipment record schema and an optional loader branch. Equipment-only failure must return a dataset status and must not reject the valid Overview snapshot.

- [ ] Run GREEN with the same focused command. Existing Overview and replay loader tests must also pass.

- [ ] Commit:
    git add web/src/data/schema.ts web/src/data/loadSnapshot.ts web/src/data/loadSnapshot.test.ts
    git commit -m "feat: expose equipment snapshot state"

### Task 2: Add pure query and URL-state helpers

**Files:** Create web/src/features/equipment/equipmentTable.ts, equipmentTable.test.ts, equipmentUrlState.ts, and equipmentUrlState.test.ts.

**Interfaces:** Implement filterEquipment(records, query, terminal), sortEquipment(records, column, direction), readEquipmentUrlState(search), and writeEquipmentUrlState(state). Defaults are query "", sort equipment_id, direction asc, and equipmentId null.

- [ ] Write failing tests for case-insensitive equipment-ID search, terminal filtering, numeric ascending/descending sort, stable ties, invalid URL values, default omission, and selected-equipment round trips.

    expect(filterEquipment(records, "qc-00", "TM-001")).toEqual([records[0]]);
    expect(sortEquipment(records, "availability", "asc").map((row) => row.equipment_id))
      .toEqual(["QC-002", "QC-001"]);

- [ ] Run RED:
    npx vitest run --pool=forks --maxWorkers=1 src/features/equipment/equipmentTable.test.ts src/features/equipment/equipmentUrlState.test.ts --reporter=dot

- [ ] Implement copied-array stable sorting, numeric comparisons, URLSearchParams encoding, and safe normalization.

- [ ] Run GREEN with the same command.

- [ ] Commit:
    git add web/src/features/equipment
    git commit -m "feat: add equipment query state helpers"

### Task 3: Render table and detail components

**Files:** Create EquipmentTable.tsx and test, EquipmentDetail.tsx and test.

**Interfaces:** EquipmentTable consumes records, query, terminal, sort, direction, onQueryChange, onSortChange, and onSelect. EquipmentDetail consumes record and onBack. Equipment IDs expose accessible names Open equipment <id>.

- [ ] Write failing component tests for the native table name, eight headers, visible values, aria-sort, labelled search, keyboard activation, detail labels including MTBF, and Unavailable for nullable metrics.

    expect(screen.getByRole("table", { name: "Equipment fleet" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Availability" }))
      .toHaveAttribute("aria-sort", "ascending");

- [ ] Run RED:
    npx vitest run --pool=forks --maxWorkers=1 src/features/equipment/EquipmentTable.test.tsx src/features/equipment/EquipmentDetail.test.tsx --reporter=dot

- [ ] Implement a semantic table, sortable header buttons, labelled search input, text state values, and detail definitions. Do not fabricate values.

- [ ] Run GREEN with the same command.

- [ ] Commit:
    git add web/src/features/equipment/EquipmentTable.tsx web/src/features/equipment/EquipmentTable.test.tsx web/src/features/equipment/EquipmentDetail.tsx web/src/features/equipment/EquipmentDetail.test.tsx
    git commit -m "feat: render equipment fleet and detail views"

### Task 4: Compose page and integrate routing

**Files:** Create EquipmentPage.tsx and test; modify web/src/app/App.tsx and App.test.tsx.

**Interfaces:** EquipmentPage consumes dataset: EquipmentDatasetState and global filters. It owns normalized EquipmentUrlState and one history source. App renders EquipmentPage for hash equipment, Overview for overview or unknown hashes.

- [ ] Write failing tests for the equipment route, absent/malformed/unavailable/empty states, no-results state, global terminal filtering, URL search and sort updates, detail selection, back-link restoration, unknown equipment ID, and stale warning placement.

    window.location.hash = "#equipment";
    render(<App loadData={() => Promise.resolve(snapshotWithEquipment)} />);
    expect(await screen.findByRole("heading", { name: "Equipment fleet" }))
      .toBeInTheDocument();

- [ ] Run RED:
    npx vitest run --pool=forks --maxWorkers=1 src/features/equipment/EquipmentPage.test.tsx src/app/App.test.tsx --reporter=dot

- [ ] Implement the page composition and hash routing. Pass the already loaded dataset state through; do not create a second loader or weaken stale recovery.

- [ ] Run GREEN with the same command.

- [ ] Commit:
    git add web/src/features/equipment web/src/app/App.tsx web/src/app/App.test.tsx
    git commit -m "feat: add equipment exploration route"

### Task 5: Apply responsive styling and update records

**Files:** Modify web/src/styles.css and docs/product/BACKLOG.md.

- [ ] Add table overflow containment, 44 px search/sort targets, aligned numeric columns, visible state text, detail layout, and narrow-screen rules that hide only lower-priority columns.
- [ ] Run the complete frontend suite:
    npx vitest run --pool=forks --maxWorkers=1 --reporter=dot
    Expected: every frontend test passes.
- [ ] Update the current backlog action to PF-019, stating PF-018 is complete.
- [ ] Commit:
    git add web/src/styles.css docs/product/BACKLOG.md
    git commit -m "docs: advance backlog after equipment exploration"

### Task 6: Release-level verification

**Files:** No source changes expected.

- [ ] Run:
    npx vitest run --pool=forks --maxWorkers=1 --reporter=dot
    npm run typecheck
    $env:VITE_BASE_PATH='/PortFlow/'; npm run build
    npm run verify:pages
    git diff --check
- [ ] Confirm all commands succeed, the Pages path is verified, and the worktree is clean.
- [ ] Review the final commit list and report any unavailable Python test tooling separately rather than hiding it.
