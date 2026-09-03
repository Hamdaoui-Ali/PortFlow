# Deterministic Replay State Machine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure reducer that deterministically replays validated `ReplayEventV1` records using explicit virtual-time ticks.

**Architecture:** `replayMachine.ts` owns immutable replay state, action types, input normalization, and reducer transitions. It has no React, timers, DOM, or wall-clock dependencies; PF-021 will provide the timer/UI adapter later. Events are ordered by parsed epoch milliseconds and applied when a `TICK` reaches their timestamp.

**Tech Stack:** TypeScript, React workspace conventions, Vitest 4, existing `ReplayEventV1` snapshot type.

**Spec:** `docs/superpowers/specs/2026-09-03-replay-state-machine-design.md`

## Global Constraints

- PF-020 changes only `web/src/features/replay/replayMachine.ts` and `web/src/features/replay/replayMachine.test.ts`.
- Replay state never reads the wall clock or calls browser APIs.
- Reducer transitions return new state and never mutate input events or arrays.
- Ticks use `deltaMs × speed`; negative tick values are ignored.
- Supported speeds are exactly `0.5`, `1`, `2`, and `4`.
- Event ordering uses parsed epoch timestamps with original input order as the stable tie-breaker.
- The final event is applied exactly once and moves the machine to `complete`.
- Reduced motion preserves the same logical event order and reducer results.
- Do not add dependencies, timers, UI, routing, snapshot loading, or live-data claims.

---

### Task 1: Define replay state, initialization, ordering, and restart actions

**Files:**
- Create: `web/src/features/replay/replayMachine.ts`
- Create: `web/src/features/replay/replayMachine.test.ts`

**Interfaces:**
- Consumes: `ReplayEventV1` from `web/src/data/schema.ts`.
- Produces:
  - `ReplayStatus = "idle" | "playing" | "paused" | "complete"`;
  - `ReplaySpeed = 0.5 | 1 | 2 | 4`;
  - `ReplayState` with `status`, `events`, `currentIndex`, `virtualTime`, `appliedEvents`, `speed`, and `reducedMotion`;
  - `ReplayAction` variants `START`, `PAUSE`, `RESUME`, `RESET`, `SET_SPEED`, and `TICK`;
  - `createReplayState(events: ReplayEventV1[], options?: { speed?: ReplaySpeed; reducedMotion?: boolean }): ReplayState`;
  - `replayReducer(state: ReplayState, action: ReplayAction): ReplayState`.

- [ ] **Step 1: Write failing initialization and ordering tests**

Add fixtures with UTC timestamps, offset timestamps, equal timestamps, and an empty list. Test the exact initial state shape:

```ts
const state = createReplayState(events, { speed: 2, reducedMotion: true });

expect(state.status).toBe("idle");
expect(state.currentIndex).toBe(-1);
expect(state.virtualTime).toBe(Date.parse("2026-09-02T00:00:00Z"));
expect(state.appliedEvents).toEqual([]);
expect(state.speed).toBe(2);
expect(state.reducedMotion).toBe(true);
```

Assert that offset timestamps sort by their instant, equal timestamps preserve input order, and an empty list returns `status: "complete"`, `currentIndex: -1`, `virtualTime: null`, and no applied events.

- [ ] **Step 2: Run the focused tests to verify RED**

Run from `web`:

```bash
npx vitest run src/features/replay/replayMachine.test.ts --pool=forks --maxWorkers=1
```

Expected: FAIL because `replayMachine.ts` and its exported functions do not exist.

- [ ] **Step 3: Implement initialization and stable event normalization**

Create the state/action types and implement `createReplayState`. Copy the input array, map each event with its original index, sort by `Date.parse(event.event_timestamp)` then original index, and expose the sorted event records. Initialize non-empty virtual time to the first sorted event’s epoch timestamp; initialize empty replay as complete.

- [ ] **Step 4: Add restart and policy action tests**

Add tests proving:

```ts
const started = replayReducer(createReplayState(events), { type: "START" });
expect(started.status).toBe("playing");
expect(started.currentIndex).toBe(0);
expect(started.appliedEvents).toEqual([started.events[0]]);

const changed = replayReducer(started, { type: "SET_SPEED", speed: 4 });
expect(changed.speed).toBe(4);

const reset = replayReducer(changed, { type: "RESET" });
expect(reset.status).toBe("idle");
expect(reset.currentIndex).toBe(-1);
expect(reset.appliedEvents).toEqual([]);
expect(reset.speed).toBe(4);
```

Test that `START` always restarts from the first event, `RESET` preserves speed and reduced-motion policy, and redundant `PAUSE`/`RESUME` actions do not change unrelated state.

- [ ] **Step 5: Implement start, reset, speed, pause, and resume transitions**

Implement `START` as a restart that applies the first event for non-empty input and returns `complete` unchanged for empty input. Implement `RESET` by recreating the initial cursor from the existing normalized events while retaining `speed` and `reducedMotion`. Implement `SET_SPEED` as a state-only update. Implement `PAUSE` only for `playing` and `RESUME` only for `paused`.

- [ ] **Step 6: Run focused tests to verify GREEN**

```bash
npx vitest run src/features/replay/replayMachine.test.ts --pool=forks --maxWorkers=1
```

Expected: all Task 1 tests pass.

- [ ] **Step 7: Commit Task 1**

```bash
git add web/src/features/replay/replayMachine.ts web/src/features/replay/replayMachine.test.ts
git commit -m "feat: define deterministic replay state"
```

---

### Task 2: Implement virtual-time ticks and completion

**Files:**
- Modify: `web/src/features/replay/replayMachine.ts`
- Modify: `web/src/features/replay/replayMachine.test.ts`

**Interfaces:**
- Consumes: `ReplayState` and `ReplayAction` from Task 1.
- Produces: deterministic `TICK` behavior for every supported speed and event gap.

- [ ] **Step 1: Write failing tick and completion tests**

Use events at `00:00:00`, `00:00:05`, and `00:00:12` UTC. Prove the first event is applied by `START`, then:

```ts
let state = replayReducer(createReplayState(events, { speed: 1 }), { type: "START" });
state = replayReducer(state, { type: "TICK", deltaMs: 5_000 });

expect(state.virtualTime).toBe(Date.parse("2026-09-02T00:00:05Z"));
expect(state.appliedEvents).toHaveLength(2);
expect(state.currentIndex).toBe(1);
```

Add a tick that crosses multiple event timestamps and assert all reached events are appended in order. Add a tick that reaches the final timestamp and assert `status: "complete"`, final index, and no duplicate event when another tick or `RESUME` follows. Add tests that `TICK` while idle/paused/complete and negative `deltaMs` are no-ops.

- [ ] **Step 2: Run the focused tests to verify RED**

```bash
npx vitest run src/features/replay/replayMachine.test.ts --pool=forks --maxWorkers=1
```

Expected: FAIL on the new tick assertions because `TICK` is not implemented.

- [ ] **Step 3: Implement scaled virtual-time advancement**

For a playing state and non-negative `deltaMs`, compute `nextVirtualTime = state.virtualTime + deltaMs * state.speed`. Find events after `currentIndex` whose parsed timestamp is less than or equal to `nextVirtualTime`; append them once, update `currentIndex` to the last reached event, and set `virtualTime` to `nextVirtualTime` unless the final event was reached. When the final event is reached, set `virtualTime` to its timestamp and `status` to `complete`.

- [ ] **Step 4: Add speed and reduced-motion invariance tests**

Prove that the same logical sequence is reached faster at `4x` than at `1x`, while the applied event order is identical. Create two states with the same events and action sequence, differing only in `reducedMotion`, and assert their status, cursor, virtual time, and applied events are equal after identical actions.

- [ ] **Step 5: Implement speed-independent reduced-motion behavior**

Keep `reducedMotion` as a policy field only. Do not branch reducer event ordering or timestamps on it. Ensure `SET_SPEED` accepts only the `ReplaySpeed` union at compile time and preserves all other state fields.

- [ ] **Step 6: Run focused tests to verify GREEN**

```bash
npx vitest run src/features/replay/replayMachine.test.ts --pool=forks --maxWorkers=1
```

Expected: all Task 1 and Task 2 tests pass.

- [ ] **Step 7: Commit Task 2**

```bash
git add web/src/features/replay/replayMachine.ts web/src/features/replay/replayMachine.test.ts
git commit -m "feat: advance replay with virtual time"
```

---

### Task 3: Harden immutability, invalid actions, and release verification

**Files:**
- Modify: `web/src/features/replay/replayMachine.ts`
- Modify: `web/src/features/replay/replayMachine.test.ts`

**Interfaces:**
- Consumes: the complete reducer contract from Tasks 1–2.
- Produces: a release-ready PF-020 machine with documented edge behavior and no UI coupling.

- [ ] **Step 1: Write failing edge-case and immutability tests**

Capture the input array and state arrays before each reducer call. Assert that `START`, `TICK`, and `RESET` leave the original arrays unchanged. Add tests that malformed action values supplied through an `as ReplayAction` boundary return the same logical state without throwing. Test `TICK` with `deltaMs: 0`, `NaN`, and `Infinity` as invalid/no-op inputs.

- [ ] **Step 2: Run the focused tests to verify RED**

```bash
npx vitest run src/features/replay/replayMachine.test.ts --pool=forks --maxWorkers=1
```

Expected: FAIL for any mutation or invalid-input behavior not yet guarded.

- [ ] **Step 3: Harden reducer boundaries**

Use copied arrays for every changed collection. Return the prior state for unsupported actions, non-finite tick values, negative ticks, and invalid speed values. Keep the reducer exhaustive for typed actions while retaining a safe default for runtime inputs.

- [ ] **Step 4: Run focused and full verification**

```bash
npx vitest run src/features/replay/replayMachine.test.ts --pool=forks --maxWorkers=1
npx vitest run --pool=forks --maxWorkers=1 --reporter=dot
npm run typecheck
$env:VITE_BASE_PATH='/PortFlow/'; npm run build
npm run verify:pages
git diff --check
```

Expected: focused tests pass, the full frontend suite passes, typecheck/build/Pages verification succeed, and `git diff --check` reports no whitespace errors.

- [ ] **Step 5: Commit Task 3**

```bash
git add web/src/features/replay/replayMachine.ts web/src/features/replay/replayMachine.test.ts
git commit -m "test: harden replay state boundaries"
```

- [ ] **Step 6: Advance the backlog**

Update `docs/product/BACKLOG.md` so the current next action becomes PF-021 and records that PF-020 is complete. Run `git diff --check`, then commit the documentation separately:

```bash
git add docs/product/BACKLOG.md
git commit -m "docs: advance backlog after replay state"
```

## Final handoff

After all tasks, request a review of the complete PF-020 commit range. Report any unavailable browser or Python tooling separately. Do not start PF-021 in this plan; its UI and timer adapter must be designed as a separate task.
