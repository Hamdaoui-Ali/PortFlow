# Live Demo Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dedicated, accessible PortFlow Live Demo page that controls the deterministic replay and presents honest simulation activity with changing replay-derived status.

**Architecture:** Keep `replayMachine` pure and place browser timing in a page-local adapter. Use small presentational components for disclosure, controls, KPIs, and activity; derive all visible replay values from the machine state and validated snapshot records. Extend the existing hash route and shell only as needed.

**Tech Stack:** React 19, TypeScript, Vitest 4, Testing Library, native browser timers, existing Zod snapshot schemas, and the existing PortFlow CSS system.

**Spec:** `docs/superpowers/specs/2026-09-03-live-demo-interface-design.md`

## Global Constraints

- PF-021 is a dedicated `#live-demo` route rendered by the existing application shell.
- The existing `replayMachine` remains the pure state-machine boundary; browser timers live only in the page adapter.
- The page uses only validated `SnapshotV1.event_replay` and overview data; it does not add a backend, polling, analytics, or a new snapshot contract.
- The interface persistently labels the experience as simulated and never implies live operational data.
- Speed selection supports exactly `0.5x`, `1x`, `2x`, and `4x`.
- Start applies the full initial timestamp group; pause, resume, reset, completion, and repeated actions preserve the replay-machine contract.
- `prefers-reduced-motion` changes presentation only; it does not change actions, event order, virtual time, or derived values.
- Missing, empty, malformed, or unavailable replay data renders an honest state and never fabricates a demo.
- Every interactive control has an accessible name, visible focus state, and keyboard operation.
- The activity list is not an unbounded live region; bounded status text announces replay state and the latest applied event.
- PF-021 does not include PF-022, PF-023, global replay context, server-side playback, new event fields, or external design dependencies.

## File map

- Create `web/src/features/replay/replayPresentation.ts` for pure view-model derivation from `ReplayState` and overview context.
- Create `web/src/features/replay/replayPresentation.test.ts` for deterministic KPI, current-state, progress, and event-label tests.
- Create `web/src/features/replay/ReplayDisclosure.tsx` for the persistent simulation disclosure.
- Create `web/src/features/replay/ReplayControls.tsx` for native replay controls and accessible labels.
- Create `web/src/features/replay/ReplayKpiStrip.tsx` for current-state, availability, progress, and overview-context values.
- Create `web/src/features/replay/ReplayActivityFeed.tsx` for the chronological applied-event list.
- Create `web/src/features/replay/LiveDemoPage.tsx` for snapshot-state handling, reducer ownership, timer lifecycle, and composition.
- Create `web/src/features/replay/LiveDemoPage.test.tsx` for page behavior and accessibility checks.
- Modify `web/src/app/App.tsx` to recognize `#live-demo` and render `LiveDemoPage`.
- Modify `web/src/app/App.test.tsx` for route and snapshot wiring coverage.
- Modify `web/src/styles.css` for the Live Demo layout, controls, status, feed, and narrow-screen behavior.
- Modify `docs/product/BACKLOG.md` after verification to advance the next action to PF-022.

---

### Task 1: Define replay presentation view models

**Files:**
- Create: `web/src/features/replay/replayPresentation.ts`
- Create: `web/src/features/replay/replayPresentation.test.ts`

**Interfaces:**
- Consumes: `ReplayState` from `./replayMachine`, `OverviewV1` and `ReplayEventV1` from `../../data/schema`.
- Produces:
  - `ReplayViewModel` with `currentEvent: ReplayEventV1 | null`, `progressLabel: string`, `availabilityLabel: string`, `currentStateLabel: string`, `sourceAvailabilityLabel: string`, and `latestEventLabel: string`;
  - `deriveReplayViewModel(state: ReplayState, overview: OverviewV1): ReplayViewModel`;
  - `formatReplayTimestamp(timestamp: string): string`;
  - `formatReplayEvent(event: ReplayEventV1): string`.

- [ ] **Step 1: Write failing view-model tests**

Create fixed fixtures with active, warning, unavailable, and idle events. Test that:

```ts
const state = replayReducer(createReplayState(events), { type: "START" });
const model = deriveReplayViewModel(state, overview);

expect(model.currentEvent?.event_id).toBe("evt-1");
expect(model.progressLabel).toBe("1 of 4 events");
expect(model.availabilityLabel).toBe("Available");
expect(model.currentStateLabel).toBe("ACTIVE");
expect(model.sourceAvailabilityLabel).toBe("94.4%");
```

Also test no applied events, unavailable events, completion at 4 of 4, UTC timestamp formatting, and that event labels include event id, equipment id, terminal, and state.

- [ ] **Step 2: Run focused tests to verify RED**

Run from `web`:

```bash
npx vitest run src/features/replay/replayPresentation.test.ts --pool=forks --maxWorkers=1
```

Expected: FAIL because the view-model module and exports do not exist.

- [ ] **Step 3: Implement pure derivation**

Use `state.appliedEvents.at(-1) ?? null` for the current event. Format progress as `${appliedEvents.length} of ${events.length} events`, use `Available`/`Unavailable` from the current event’s boolean, show `Unavailable` when no current event exists, format the overview availability percentage to one decimal place, and format timestamps using `Intl.DateTimeFormat` with `timeZone: "UTC"`.

Do not calculate historical aggregate availability from replay events. The overview percentage is source context; current event availability and replay progress are simulation output.

- [ ] **Step 4: Run focused tests to verify GREEN**

```bash
npx vitest run src/features/replay/replayPresentation.test.ts --pool=forks --maxWorkers=1
```

Expected: all view-model tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add web/src/features/replay/replayPresentation.ts web/src/features/replay/replayPresentation.test.ts
git commit -m "feat: derive live demo replay presentation"
```

---

### Task 2: Build the Live Demo page and replay controls

**Files:**
- Create: `web/src/features/replay/ReplayDisclosure.tsx`
- Create: `web/src/features/replay/ReplayControls.tsx`
- Create: `web/src/features/replay/ReplayKpiStrip.tsx`
- Create: `web/src/features/replay/ReplayActivityFeed.tsx`
- Create: `web/src/features/replay/LiveDemoPage.tsx`
- Create: `web/src/features/replay/LiveDemoPage.test.tsx`

**Interfaces:**
- Consumes: `ReplayState`, `ReplayAction`, and `replayReducer` from `./replayMachine`; `ReplayViewModel` from `./replayPresentation`; validated replay and overview records from `SnapshotV1`.
- Produces: `LiveDemoPage({ events, overview }: { events?: ReplayEventV1[]; overview: OverviewV1 })` and independently testable presentational components. `undefined` represents a missing, malformed, or unavailable replay dataset; `[]` represents a published empty replay.

- [ ] **Step 1: Write failing page and component tests**

Test these behaviors with fake timers and fixed replay fixtures:

```tsx
render(<LiveDemoPage events={events} overview={overview} />);
expect(screen.getByRole("heading", { name: "Live Demo" })).toBeInTheDocument();
expect(screen.getByText("Simulation — not live operational data")).toBeInTheDocument();
expect(screen.getByRole("button", { name: "Start replay" })).toBeInTheDocument();

await user.click(screen.getByRole("button", { name: "Start replay" }));
expect(screen.getByRole("status")).toHaveTextContent("Replay playing");

await act(async () => { vi.advanceTimersByTime(5_000); });
expect(screen.getByRole("list", { name: "Replay activity" })).toHaveTextContent("evt-2");
```

Cover pause/resume, reset, each speed option, completion, timer cleanup after pause/reset/unmount, keyboard activation, bounded status announcements, reduced-motion media preference, and absent/empty event fixtures at the page boundary.

- [ ] **Step 2: Run focused tests to verify RED**

```bash
npx vitest run src/features/replay/LiveDemoPage.test.tsx --pool=forks --maxWorkers=1
```

Expected: FAIL because the page and components do not exist.

- [ ] **Step 3: Implement disclosure and native controls**

`ReplayDisclosure` renders the exact persistent disclosure text. `ReplayControls` renders native buttons and a labeled select. Button labels must reflect state: `Start replay`, `Pause replay`, `Resume replay`, and `Reset replay`; completion keeps Reset available and disables ticking through the page adapter. The speed select exposes `0.5x`, `1x`, `2x`, and `4x` values.

- [ ] **Step 4: Implement KPI and activity presentation**

`ReplayKpiStrip` renders four labeled values from `ReplayViewModel`: current equipment state, current availability, replay progress, and source overview availability. `ReplayActivityFeed` renders a semantic `ul` with `aria-label="Replay activity"`; each `li` includes the formatted event label and timestamp. Do not apply `aria-live` to the list.

- [ ] **Step 5: Implement the page-local reducer and timer adapter**

Initialize with `createReplayState(events, { reducedMotion: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false })`. Keep the reducer state in `useReducer`. Dispatch `START`, `PAUSE`, `RESUME`, `RESET`, and `SET_SPEED` from controls. While status is `playing`, use one `setInterval` that dispatches `{ type: "TICK", deltaMs: 1000 }`; clear it whenever status is not `playing` and in the effect cleanup. The timer must not use `Date.now()` or mutate replay state outside the reducer.

Render the page heading, disclosure, status region, controls, KPI strip, and activity feed in that order. The status text must include `Replay idle`, `Replay playing`, `Replay paused`, or `Replay complete`; when an event is newly applied, include its formatted label in the bounded status message.

- [ ] **Step 6: Add reduced-motion and dataset boundary behavior**

Keep reducer actions identical in reduced-motion mode. If the page receives an empty event list, render the page disclosure and an honest `Replay has no events` status without starting a timer. If `events` is `undefined`, render the page disclosure and `Replay dataset not published` without creating a replay timer. Task 3 passes the optional snapshot field without converting it to an empty array.

- [ ] **Step 7: Run focused tests to verify GREEN**

```bash
npx vitest run src/features/replay/LiveDemoPage.test.tsx --pool=forks --maxWorkers=1
npx vitest run src/features/replay/replayPresentation.test.ts --pool=forks --maxWorkers=1
```

Expected: all page, component, and view-model tests pass.

- [ ] **Step 8: Commit Task 2**

```bash
git add web/src/features/replay
git commit -m "feat: build live demo replay interface"
```

---

### Task 3: Integrate the route, snapshot states, and responsive styles

**Files:**
- Modify: `web/src/app/App.tsx`
- Modify: `web/src/app/App.test.tsx`
- Modify: `web/src/styles.css`

**Interfaces:**
- Consumes: `LiveDemoPage` from `../features/replay/LiveDemoPage`; `SnapshotV1.event_replay`; existing `readRoute`, `AppShell`, stale snapshot handling, and `AppFilters`.
- Produces: `#live-demo` rendering with the same shell, global filter behavior, and honest replay dataset boundaries.

- [ ] **Step 1: Write failing route and dataset-state tests**

Add tests that set `window.location.hash = "#live-demo"` and assert `Live Demo` renders. Test a ready snapshot with events, a ready snapshot without `event_replay`, and a ready snapshot with an empty replay array. Assert the disclosure remains visible for the latter two and no replay controls start a timer. Test stale snapshots preserve the existing stale notice above the Live Demo content. Test unknown hashes still fall back to Overview.

- [ ] **Step 2: Run App tests to verify RED**

```bash
npx vitest run src/app/App.test.tsx --pool=forks --maxWorkers=1
```

Expected: the new Live Demo route/state assertions fail.

- [ ] **Step 3: Add route recognition and page rendering**

Extend `AppRoute` with `"live-demo"`, return it from `readRoute()` for `#live-demo`, and render `LiveDemoPage` with `snapshot.event_replay` and `snapshot.overview`. For omitted replay data, the page renders an honest message stating `Replay dataset not published` while preserving the persistent simulation disclosure. Keep stale notices in the same location as Equipment and Incidents.

- [ ] **Step 4: Add focused route and dataset assertions**

Assert the Live Demo route renders the heading, disclosure, and controls for ready replay data; the omitted and empty cases render their exact honest messages; and the page never says the data is live.

- [ ] **Step 5: Add responsive and accessibility styles**

Add styles for the Live Demo header, disclosure, control group, KPI cards, status region, feed, state badges, and narrow screens. Use existing tokens, preserve visible focus outlines, keep controls at least 44px high, and make the feed/KPI regions collapse to one column below the existing mobile breakpoint. Add `@media (prefers-reduced-motion: reduce)` rules that remove transitions/animations from the new classes.

- [ ] **Step 6: Run focused tests to verify GREEN**

```bash
npx vitest run src/app/App.test.tsx --pool=forks --maxWorkers=1
npx vitest run src/features/replay/LiveDemoPage.test.tsx --pool=forks --maxWorkers=1
```

Expected: route, dataset, and page tests pass.

- [ ] **Step 7: Commit Task 3**

```bash
git add web/src/app/App.tsx web/src/app/App.test.tsx web/src/styles.css
git commit -m "feat: integrate live demo route"
```

---

### Task 4: Harden verification and advance the backlog

**Files:**
- Modify: `web/src/features/replay/replayPresentation.test.ts`
- Modify: `web/src/features/replay/LiveDemoPage.test.tsx`
- Modify: `web/src/app/App.test.tsx`
- Modify: `docs/product/BACKLOG.md`

**Interfaces:**
- Consumes: complete PF-021 implementation from Tasks 1–3.
- Produces: release-ready Live Demo behavior with documented completion and PF-022 as the next action.

- [ ] **Step 1: Add boundary and regression tests**

Add explicit assertions for all required controls’ accessible names, exact simulation disclosure copy, current-state derivation after warning/unavailable events, reset preserving speed, completion disabling timer work, reduced-motion result equivalence, and stale/omitted/empty dataset messages.

- [ ] **Step 2: Run the focused PF-021 suite**

```bash
npx vitest run src/features/replay/replayPresentation.test.ts src/features/replay/LiveDemoPage.test.tsx src/app/App.test.tsx --pool=forks --maxWorkers=1
```

Expected: all PF-021-focused tests pass.

- [ ] **Step 3: Run full release verification**

```bash
npm test -- --run --pool=forks --maxWorkers=1 --reporter=dot
npm run typecheck
$env:VITE_BASE_PATH='/PortFlow/'; npm run build
npm run verify:pages
git diff --check
```

Expected: the full frontend suite, typecheck, build, Pages verification, and whitespace checks pass.

- [ ] **Step 4: Update the backlog**

Change the current next action to PF-022 and record that PF-021 is complete. Do not alter unrelated task text.

- [ ] **Step 5: Commit verification and backlog separately**

```bash
git add web/src/features/replay/replayPresentation.test.ts web/src/features/replay/LiveDemoPage.test.tsx web/src/app/App.test.tsx
git commit -m "test: harden live demo boundaries"
git add docs/product/BACKLOG.md
git commit -m "docs: advance backlog after live demo"
```

## Final handoff

Review the complete PF-021 commit range before finishing. Report any unavailable browser tooling separately. Do not start PF-022 in this plan.
