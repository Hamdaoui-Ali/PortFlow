# PF-023 Responsive and Accessibility Design

## Status

Approved design for implementation planning.

## Goal

Make every approved PortFlow view usable without a mouse and on narrow screens,
with automated accessibility checks and a repeatable manual keyboard checklist.

## Scope

PF-023 covers the existing Overview, Equipment, Incidents, Live Demo, and Data
Health views. It will correct:

- semantic landmarks, headings, labels, table structure, and status text;
- keyboard focus order, visible focus, and detail-page return focus;
- chart summaries and non-color status communication;
- contrast and touch-target sizing;
- mobile stacking, bounded table overflow, and page-level horizontal overflow;
- reduced-motion behavior.

The work preserves the existing PortFlow visual system, native controls, table
semantics, URL/history behavior, static data boundary, and feature boundaries.
It does not add a new interaction model, redesign the product, or introduce a
browser E2E runner.

## Accessibility test strategy

Add a minimal `axe-core`-based check to the existing Vitest/jsdom and Testing
Library environment. Use one shared helper under `web/src/test/` and a
route-focused suite at `web/e2e/accessibility.spec.ts`, as named by the
backlog. The suite renders the real `App` with deterministic fixtures and
checks each approved route.

The automated check must report zero axe violations for Overview, Equipment,
Incidents, Live Demo, and Data Health. It must also assert the main landmark,
page heading, named interactive controls, non-fabricated status/data states,
and route-specific semantic requirements.

The manual checklist remains required for behavior that axe cannot prove:

1. `Tab` from the address bar reaches the skip link and then primary content.
2. Focus indicators remain visible on links, selects, buttons, details, and
   table controls.
3. Detail-page back actions return focus to the relevant heading/list context.
4. At 320px and 375px widths, no page-level horizontal scroll appears.
5. Reduced motion removes animation/transition dependence without hiding state
   changes.

## Component boundaries

`AppShell` owns skip navigation, the main landmark, global filters, route-aware
navigation, and mobile navigation. Feature components own their headings,
tables, charts, buttons, status regions, and detail transitions. `styles.css`
owns shared focus visibility, touch targets, responsive layout, overflow, and
reduced-motion rules.

Do not create a second application or duplicate feature markup for testing.
Do not replace native `select`, `button`, `details`, or `table` elements with
custom widgets unless an existing behavior is impossible to make accessible.

## Route acceptance matrix

### Overview

Verify heading hierarchy, KPI definition disclosures, chart text summary,
status text, skip link, focus visibility, and absence of page-level horizontal
overflow.

### Equipment

Verify search labeling, sortable headers with correct `aria-sort`,
keyboard-openable equipment controls, detail-page heading/back focus, and
bounded table overflow.

### Incidents

Verify filter labels, sorting state, severity text, keyboard detail navigation,
detail-page heading/back focus, and bounded table overflow.

### Live Demo

Verify simulation disclosure, named control states, status updates, reduced
motion equivalence, and absence of a feed-wide live region.

### Data Health

Verify status explanation, semantic timestamps, evidence-table headers,
honest unavailable rejection evidence, and one-column mobile KPI stacking.

## Data and error behavior

Accessibility changes must preserve honest loading, unavailable, malformed,
empty, stale, and invalid states. Status meaning must be visible as text and
must not depend on color alone. Existing cached-snapshot behavior remains
unchanged.

If an accessibility fix exposes a missing product decision or requires a new
interaction model, stop at the boundary and record it for a later backlog
task rather than expanding PF-023 silently.

## Responsive rules

- No page-level horizontal scroll at 320px or 375px.
- Tables may scroll inside clearly bounded table regions when their data
  cannot fit, while the surrounding page remains within the viewport.
- KPI rails and analytical grids collapse to one column where the content
  would otherwise overflow or become unreadable.
- Interactive controls retain at least 44px touch targets.
- Focus outlines remain visible against all approved surfaces.
- Reduced-motion users receive the same logical state and content without
  relying on animation.

## Verification and completion

PF-023 is complete only when:

- the axe route suite passes with zero violations;
- route/component tests pass for all listed semantic and keyboard behaviors;
- the manual keyboard and viewport checklist has no blocker;
- full frontend tests pass;
- TypeScript typecheck passes;
- the `/PortFlow/` production build passes;
- Pages-path verification passes;
- `git diff --check` passes.

## Non-goals

- a browser E2E framework or browser installation;
- a visual redesign or new design system;
- new data, metrics, routes, or backend behavior;
- changing snapshot schemas or pipeline logic;
- replacing native controls with custom accessibility widgets;
- end-to-end data reconciliation, which belongs to PF-024.
