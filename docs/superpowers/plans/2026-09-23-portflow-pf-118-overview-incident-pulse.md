# PF-118 Overview incident pulse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox ( ) syntax for tracking.

**Goal:** Add a deterministic, accessible incident pulse to the Overview route so operators can move from the top three attention-worthy incidents to the existing lifecycle detail view.

**Architecture:** Keep the feature inside web/src/features/overview. A pure helper converts the existing optional IncidentDatasetState into either a bounded ranked view or an honest dataset state; a presentational component renders that view. App passes the already-loaded incident dataset through OverviewPage, so no fetch, schema, route, or backend change is required.

**Tech Stack:** React 19, TypeScript, Zod-validated snapshot types, Vitest, Testing Library, Vite, and the existing web/src/styles.css convention.

**Spec:** docs/superpowers/specs/2026-09-23-portflow-pf-118-overview-incident-pulse-design.md

## Global Constraints

- Use the existing IncidentDatasetState and IncidentRecordV1 snapshot contract; do not add a network request or mutate public data.
- Show at most three records, ranked open-first, then severity, newest opening instant, then incident ID.
- Preserve native links in the form ?incident=<encoded-id>#incidents.
- Use semantic headings, lists, links, time, and output elements for dataset messages.
- Keep component props and helper inputs read-only.
- Keep the existing PortFlow typography, cobalt/teal/amber status language, borders, and responsive breakpoints.
- Run focused tests after each implementation task and the full repository verification before PR handoff.

## Review Focus

- A ready dataset with more than three records remains bounded and deterministically ranked; helper tests cover limit, open status, severity, timestamp offsets, and ID ties.
- undefined, absent, empty, unavailable, and malformed inputs do not appear as an empty list; component tests cover every message and the OUTPUT element.
- Incident links preserve native browser navigation and the existing detail route; component and App integration tests assert the exact href.
- Severity remains understandable without color; component tests assert visible severity and lifecycle text.
- Narrow layouts stack pulse rows without horizontal overflow; responsive selectors and the existing build/typecheck gate cover the implementation.

---

### Task 1: Record the feature contract

Files:
- Create docs/superpowers/specs/2026-09-23-portflow-pf-118-overview-incident-pulse-design.md
- Create docs/superpowers/plans/2026-09-23-portflow-pf-118-overview-incident-pulse.md

Interfaces:
- Consumes the merged PF-117 Overview equipment pulse and the existing incident route contract.
- Produces the exact PF-118 behavior, state messages, ranking order, accessibility requirements, and verification commands used by later tasks.

- [x] Step 1: Write the design contract.
  Document the user outcome, in-scope behavior, ranking order, dataset-state messages, accessibility requirements, responsive behavior, and explicit out-of-scope items in the spec file.

- [x] Step 2: Write and self-review the implementation plan.
  Map each production file to its test-first task, scan the plan for placeholders, and ensure every Review Focus item has a test owner.

- [x] Step 3: Commit the documentation checkpoint.

    git add docs/superpowers/specs/2026-09-23-portflow-pf-118-overview-incident-pulse-design.md docs/superpowers/plans/2026-09-23-portflow-pf-118-overview-incident-pulse.md
    git commit -m "docs: define PF-118 overview incident pulse"

### Task 2: Define the deterministic incident pulse view

Files:
- Create web/src/features/overview/overviewIncidentPulseData.test.ts
- Create web/src/features/overview/overviewIncidentPulseData.ts
- Modify web/src/features/incidents/incidentData.ts
- Modify web/src/features/equipment/EquipmentContextPanel.tsx
- Test web/src/features/incidents/incidentData.test.ts

Interfaces:
- Consumes IncidentDatasetState and IncidentRecordV1 from web/src/data/schema.ts.
- Produces OVERVIEW_INCIDENT_PULSE_LIMIT, OverviewIncidentPulse, deriveOverviewIncidentPulse(dataset), and formatIncidentOpenedAt(value).

- [ ] Step 1: Write the failing helper tests.
  Create fixtures for an open critical incident, an open major incident, a resolved critical incident, and offset timestamps. Pin the following behaviors:

    it("ranks open and severe incidents before older resolved records", () => {
      const view = deriveOverviewIncidentPulse({ status: "ready", records });

      expect(view).toEqual({
        status: "ready",
        records: [records[1], records[0], records[2]],
      });
    });

    it("uses the opening instant and incident id as deterministic tie-breakers", () => {
      const view = deriveOverviewIncidentPulse({
        status: "ready",
        records: [offsetRecord, sameInstantDifferentId, records[1]],
      });

      expect(view.status).toBe("ready");
      if (view.status === "ready") {
        expect(view.records.map((record) => record.incident_id)).toEqual([
          "inc-000002",
          "inc-000004",
          "inc-000005",
        ]);
      }
    });

    it.each([
      [undefined, "absent"],
      [{ status: "empty" }, "empty"],
      [{ status: "unavailable" }, "unavailable"],
      [{ status: "malformed" }, "malformed"],
    ] as const)("preserves the %s dataset state", (dataset, status) => {
      expect(deriveOverviewIncidentPulse(dataset as IncidentDatasetState | undefined)).toEqual({ status });
    });

    it("treats a ready empty dataset as empty", () => {
      expect(deriveOverviewIncidentPulse({ status: "ready", records: [] })).toEqual({ status: "empty" });
    });

  Add a formatter assertion to incidentData.test.ts:
    expect(formatIncidentOpenedAt("2026-09-02T23:30:00-02:00")).toBe("03 Sept 2026, 01:30");

- [ ] Step 2: Run the focused tests to verify they fail.

    npm test -- --run --maxWorkers=1 src/features/overview/overviewIncidentPulseData.test.ts src/features/incidents/incidentData.test.ts

  Expected: FAIL because the new helper exports and formatter do not exist.

- [ ] Step 3: Implement the minimal pure helper and shared formatter.
  Add the bounded view and comparator:

    export const OVERVIEW_INCIDENT_PULSE_LIMIT = 3;

    export type OverviewIncidentPulse =
      | { status: "absent" | "empty" | "unavailable" | "malformed" }
      | { status: "ready"; records: IncidentRecordV1[] };

    export function deriveOverviewIncidentPulse(
      dataset: IncidentDatasetState | undefined,
    ): OverviewIncidentPulse {
      if (!dataset) return { status: "absent" };
      if (dataset.status !== "ready") return { status: dataset.status };
      if (dataset.records.length === 0) return { status: "empty" };

      return {
        status: "ready",
        records: [...dataset.records]
          .sort(comparePulsePriority)
          .slice(0, OVERVIEW_INCIDENT_PULSE_LIMIT),
      };
    }

    function comparePulsePriority(left: IncidentRecordV1, right: IncidentRecordV1): number {
      const openFirst = Number(right.status === "OPEN") - Number(left.status === "OPEN");
      if (openFirst !== 0) return openFirst;

      const severity = severityRank[right.severity] - severityRank[left.severity];
      if (severity !== 0) return severity;

      const openedAt = Date.parse(right.opened_at) - Date.parse(left.opened_at);
      if (openedAt !== 0) return openedAt;

      return left.incident_id.localeCompare(right.incident_id);
    }

  Move the existing Intl.DateTimeFormat and formatTimestamp responsibility from EquipmentContextPanel.tsx into incidentData.ts as formatIncidentOpenedAt, then import it in the equipment context component. Keep existing rendered text unchanged.

- [ ] Step 4: Run focused tests to verify they pass.

    npm test -- --run --maxWorkers=1 src/features/overview/overviewIncidentPulseData.test.ts src/features/incidents/incidentData.test.ts src/features/equipment/EquipmentContext.test.tsx

  Expected: PASS with the new helper tests and all existing incident/equipment context tests green.

- [ ] Step 5: Commit the deterministic data layer.

    git add web/src/features/overview/overviewIncidentPulseData.ts web/src/features/overview/overviewIncidentPulseData.test.ts web/src/features/incidents/incidentData.ts web/src/features/incidents/incidentData.test.ts web/src/features/equipment/EquipmentContextPanel.tsx
    git commit -m "feat: rank overview incident pulse records"

### Task 3: Render the accessible Overview incident pulse

Files:
- Create web/src/features/overview/OverviewIncidentPulse.tsx
- Create web/src/features/overview/OverviewIncidentPulse.test.tsx

Interfaces:
- Consumes IncidentDatasetState, IncidentRecordV1, deriveOverviewIncidentPulse, and formatIncidentOpenedAt.
- Produces OverviewIncidentPulse with read-only dataset?: IncidentDatasetState, a named section, native incident links, visible status/severity text, and honest output messages.

- [ ] Step 1: Write the failing component tests.
  Render a ready dataset and assert:

    it("renders ranked records with native incident links and visible context", () => {
      render(<OverviewIncidentPulse dataset={{ status: "ready", records }} />);

      expect(screen.getByRole("heading", { name: "Incident pulse" })).toBeInTheDocument();
      const pulse = screen.getByRole("list", { name: "Incident pulse records" });
      const links = screen.getAllByRole("link", { name: /^Open incident/ });

      expect(links.map((link) => link.getAttribute("href"))).toEqual([
        "?incident=inc-000002#incidents",
        "?incident=inc-000001#incidents",
      ]);
      expect(pulse).toHaveTextContent("CRITICAL");
      expect(pulse).toHaveTextContent("OPEN");
      expect(pulse).toHaveTextContent("Motor overload");
      expect(pulse).toHaveTextContent("TM-001 · QC-002");
    });

  Add an it.each covering undefined, empty, unavailable, malformed, and ready with zero records. For each case assert the message, assert getByRole("status").tagName is OUTPUT, and assert that the named list is absent.

- [ ] Step 2: Run the component tests to verify they fail.

    npm test -- --run --maxWorkers=1 src/features/overview/OverviewIncidentPulse.test.tsx

  Expected: FAIL because the component does not exist.

- [ ] Step 3: Implement the presentational component.
  Render a section with aria-labelledby="overview-incident-pulse-title", a Reliability context kicker, the Incident pulse heading, and the sentence Open and highest-severity incidents appear first in this snapshot. The ready state renders a named list. Each row includes a native anchor, a visible severity pill, the root cause, terminal/equipment/status context, and a semantic UTC time. Use encodeURIComponent for incident IDs and return output className="incident-pulse-message" for non-ready states. Do not intercept link clicks.

- [ ] Step 4: Run the component tests to verify they pass.

    npm test -- --run --maxWorkers=1 src/features/overview/OverviewIncidentPulse.test.tsx

  Expected: PASS with all semantic, link, content, and state assertions green.

- [ ] Step 5: Commit the component.

    git add web/src/features/overview/OverviewIncidentPulse.tsx web/src/features/overview/OverviewIncidentPulse.test.tsx
    git commit -m "feat: render overview incident pulse"

### Task 4: Wire the pulse into Overview and the existing route

Files:
- Modify web/src/features/overview/OverviewPage.tsx
- Modify web/src/app/App.tsx
- Modify web/src/app/App.test.tsx

Interfaces:
- Consumes snapshot.incidents already loaded by AppContent.
- Produces Overview rendering that passes the validated optional incident dataset to OverviewIncidentPulse without changing route parsing or incident detail behavior.

- [ ] Step 1: Write the failing App integration test.
  Add an incident record to the App test fixture and assert:

    it("renders the incident pulse on the Overview route", async () => {
      render(<App loadData={() => Promise.resolve({
        ...snapshot,
        incidents: { status: "ready" as const, records: [incidentRecord] },
      })} />);

      expect(await screen.findByRole("heading", { name: "Incident pulse" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Open incident inc-000002" })).toHaveAttribute(
        "href",
        "?incident=inc-000002#incidents",
      );
    });

- [ ] Step 2: Run the App test to verify it fails.

    npm test -- --run --maxWorkers=1 src/app/App.test.tsx

  Expected: FAIL because Overview does not yet receive or render the incident dataset.

- [ ] Step 3: Wire the existing snapshot field.
  Add read-only incidentDataset: SnapshotV1["incidents"] to OverviewPage, render OverviewIncidentPulse after OverviewEquipmentPulse, and pass incidentDataset={snapshot.incidents} from AppContent.

- [ ] Step 4: Run App and incident tests.

    npm test -- --run --maxWorkers=1 src/app/App.test.tsx src/features/incidents/IncidentPage.test.tsx src/features/overview/OverviewIncidentPulse.test.tsx

  Expected: PASS; the existing incident detail route remains green.

- [ ] Step 5: Commit the route integration.

    git add web/src/app/App.tsx web/src/app/App.test.tsx web/src/features/overview/OverviewPage.tsx
    git commit -m "feat: connect incident pulse to overview"

### Task 5: Add responsive styling without changing the visual system

Files:
- Modify web/src/styles.css

Interfaces:
- Consumes the class names emitted by OverviewIncidentPulse.
- Produces a bordered, readable desktop list and stacked narrow-screen rows consistent with the existing Equipment pulse and incident context treatment.

- [ ] Step 1: Add focused pulse selectors.
  Add desktop styles for incident-pulse, incident-pulse-header, incident-pulse-list, incident-pulse-item, incident-pulse-heading, incident-pulse-link, incident-pulse-meta, incident-pulse-message, and semantic time. Reuse existing CSS variables and add the same focus outline as other native links.

- [ ] Step 2: Add narrow-screen rules.
  At the existing mobile breakpoint, reduce section gap and let each row flow as a single column. At the smallest breakpoint, match existing 24px section spacing and message padding.

- [ ] Step 3: Run typecheck, tests, and build.

    npm run typecheck
    npm test -- --run --maxWorkers=1
    npm run build

  Expected: typecheck, all frontend tests, and the production build pass.

- [ ] Step 4: Commit the responsive presentation.

    git add web/src/styles.css
    git commit -m "style: add responsive incident pulse"

### Task 6: Update release records and perform final verification

Files:
- Modify docs/product/BACKLOG.md
- Modify CHANGELOG.md
- Create docs/superpowers/reviews/2026-09-23-pf-118-verification.md

Interfaces:
- Consumes the merged PF-117 checkpoint and the verified PF-118 implementation.
- Produces an accurate next-action record and a concise verification note suitable for the PR description.

- [ ] Step 1: Update release records.
  Replace the PF-117 current review checkpoint sentence with a statement that PF-117 is complete and PF-118 is the current review checkpoint. Add a top CHANGELOG entry naming the Overview incident pulse, deterministic ranking, honest dataset states, and native detail links.

- [ ] Step 2: Run repository checks.

    npm run typecheck --prefix web
    npm test --prefix web -- --run --maxWorkers=1
    npm run build --prefix web
    ./scripts/verify_r2.ps1

  Expected: generated public data remains unchanged, Python tests pass, Ruff/mypy pass, frontend tests pass, and the script exits 0.

- [ ] Step 3: Record the exact commands and observed pass counts in the verification note. Do not claim a check that was not run.

- [ ] Step 4: Commit the release records.

    git add docs/product/BACKLOG.md CHANGELOG.md docs/superpowers/reviews/2026-09-23-pf-118-verification.md
    git commit -m "docs: record PF-118 verification checkpoint"

### Task 7: Review handoff

Files:
- No additional files unless verification identifies a real failure.

- [ ] Step 1: Inspect the complete diff and branch status.

    git status --short --branch
    git diff --check origin/main...HEAD
    git log --oneline --decorate origin/main..HEAD

  Expected: only PF-118 files are changed, no whitespace errors exist, and the branch contains separate documentation, data, component, integration, style, and verification commits.

- [ ] Step 2: Push the branch and open the PR.

    git push -u origin codex/pf-118-overview-incident-pulse

  Create a PR titled PF-118: Add Overview incident pulse. Summarize the user outcome, ranking contract, state handling, tests, and verification command. Wait for CI, SonarQubeCloud, and CodeRabbit feedback.

- [ ] Step 3: Fix any reported CI or quality issue on the same branch.
  Reproduce the exact failure locally, add a regression test before the fix when behavior is involved, commit the correction separately, push, and re-check all required statuses.

- [ ] Step 4: Hand off for review.
  Once checks are green, stop at the PR review/merge handoff. Do not merge this next PR automatically; the user reviews and merges it before the next specification is selected.
