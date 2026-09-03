import { describe, expect, it } from "vitest";
import type { ReplayEventV1 } from "../../data/schema";
import { createReplayState, replayReducer, type ReplayAction } from "./replayMachine";

const event = (event_id: string, event_timestamp: string): ReplayEventV1 => ({
  available: true,
  equipment_id: "EQ-001",
  event_id,
  event_timestamp,
  state: "RUNNING",
  terminal_id: "TM-001",
});

const events = [
  event("event-2", "2026-09-02T02:00:00+02:00"),
  event("event-3", "2026-09-02T00:00:00Z"),
  event("event-1", "2026-09-02T00:00:00Z"),
];

const captureArrays = (state: ReturnType<typeof createReplayState>) => ({
  events: state.events,
  eventsContents: [...state.events],
  appliedEvents: state.appliedEvents,
  appliedEventsContents: [...state.appliedEvents],
});

const expectArraysUnchanged = (
  state: ReturnType<typeof createReplayState>,
  snapshot: ReturnType<typeof captureArrays>,
) => {
  expect(state.events).toBe(snapshot.events);
  expect(state.events).toEqual(snapshot.eventsContents);
  expect(state.appliedEvents).toBe(snapshot.appliedEvents);
  expect(state.appliedEvents).toEqual(snapshot.appliedEventsContents);
};

describe("replay machine initialization", () => {
  it("creates an idle state with stable chronological ordering", () => {
    const state = createReplayState(events, { speed: 2, reducedMotion: true });

    expect(state.status).toBe("idle");
    expect(state.events).toEqual([events[0], events[1], events[2]]);
    expect(state.currentIndex).toBe(-1);
    expect(state.virtualTime).toBe(Date.parse("2026-09-02T00:00:00Z"));
    expect(state.appliedEvents).toEqual([]);
    expect(state.speed).toBe(2);
    expect(state.reducedMotion).toBe(true);
  });

  it("returns a complete state for an empty event list", () => {
    expect(createReplayState([])).toMatchObject({
      status: "complete",
      currentIndex: -1,
      virtualTime: null,
      appliedEvents: [],
    });
  });

  it("does not mutate the input event list", () => {
    const input = [...events];

    createReplayState(input);

    expect(input).toEqual(events);
  });
});

describe("replay machine reducer", () => {
  it("starts at and applies the first event", () => {
    const initial = createReplayState(events);
    const started = replayReducer(initial, { type: "START" });

    expect(started.status).toBe("playing");
    expect(started.currentIndex).toBe(0);
    expect(started.appliedEvents).toEqual([started.events[0]]);
  });

  it("immediately completes when starting a replay with one event", () => {
    const onlyEvent = event("event-only", "2026-09-02T00:00:00Z");

    const started = replayReducer(createReplayState([onlyEvent]), { type: "START" });

    expect(started.status).toBe("complete");
    expect(started.currentIndex).toBe(0);
    expect(started.appliedEvents).toEqual([started.events[0]]);
  });

  it("always restarts from the first event", () => {
    const initial = createReplayState(events);
    const started = replayReducer(initial, { type: "START" });
    const paused = replayReducer(started, { type: "PAUSE" });
    const restarted = replayReducer(paused, { type: "START" });

    expect(restarted.status).toBe("playing");
    expect(restarted.currentIndex).toBe(0);
    expect(restarted.appliedEvents).toEqual([restarted.events[0]]);
  });

  it("leaves input and prior-state arrays unchanged across START, TICK, and RESET", () => {
    const input = [...events];
    const inputSnapshot = [...input];
    const initial = createReplayState(input);
    const initialArrays = captureArrays(initial);
    const started = replayReducer(initial, { type: "START" });

    expect(input).toEqual(inputSnapshot);
    expectArraysUnchanged(initial, initialArrays);

    const startedArrays = captureArrays(started);
    const ticked = replayReducer(started, { type: "TICK", deltaMs: 1_000 });

    expect(input).toEqual(inputSnapshot);
    expectArraysUnchanged(started, startedArrays);

    const tickedArrays = captureArrays(ticked);
    replayReducer(ticked, { type: "RESET" });

    expect(input).toEqual(inputSnapshot);
    expectArraysUnchanged(ticked, tickedArrays);
  });

  it("changes speed and reset preserves speed and reduced-motion policy", () => {
    const initial = createReplayState(events, { reducedMotion: true });
    const started = replayReducer(initial, { type: "START" });
    const changed = replayReducer(started, { type: "SET_SPEED", speed: 4 });
    const reset = replayReducer(changed, { type: "RESET" });

    expect(changed.speed).toBe(4);
    expect(reset.status).toBe("idle");
    expect(reset.currentIndex).toBe(-1);
    expect(reset.appliedEvents).toEqual([]);
    expect(reset.speed).toBe(4);
    expect(reset.reducedMotion).toBe(true);
  });

  it("pauses only while playing and resumes only while paused", () => {
    const initial = createReplayState(events);
    const redundantlyPaused = replayReducer(initial, { type: "PAUSE" });
    const started = replayReducer(initial, { type: "START" });
    const paused = replayReducer(started, { type: "PAUSE" });
    const resumed = replayReducer(paused, { type: "RESUME" });
    const redundantlyResumed = replayReducer(started, { type: "RESUME" });

    expect(redundantlyPaused).toEqual(initial);
    expect(paused.status).toBe("paused");
    expect(resumed.status).toBe("playing");
    expect(redundantlyResumed).toEqual(started);
  });

  it("advances virtual time and applies events reached at the timestamp", () => {
    const tickEvents = [
      event("event-1", "2026-09-02T00:00:00Z"),
      event("event-2", "2026-09-02T00:00:05Z"),
      event("event-3", "2026-09-02T00:00:12Z"),
    ];
    let state = replayReducer(createReplayState(tickEvents, { speed: 1 }), { type: "START" });

    state = replayReducer(state, { type: "TICK", deltaMs: 5_000 });

    expect(state.virtualTime).toBe(Date.parse("2026-09-02T00:00:05Z"));
    expect(state.appliedEvents).toHaveLength(2);
    expect(state.currentIndex).toBe(1);
  });

  it("applies every event crossed by one tick in chronological order", () => {
    const tickEvents = [
      event("event-1", "2026-09-02T00:00:00Z"),
      event("event-2", "2026-09-02T00:00:05Z"),
      event("event-3", "2026-09-02T00:00:12Z"),
    ];
    let state = replayReducer(createReplayState(tickEvents), { type: "START" });

    state = replayReducer(state, { type: "TICK", deltaMs: 12_000 });

    expect(state.appliedEvents.map(({ event_id }) => event_id)).toEqual([
      "event-1",
      "event-2",
      "event-3",
    ]);
  });

  it("completes at the final event and does not duplicate it", () => {
    const tickEvents = [
      event("event-1", "2026-09-02T00:00:00Z"),
      event("event-2", "2026-09-02T00:00:05Z"),
      event("event-3", "2026-09-02T00:00:12Z"),
    ];
    let state = replayReducer(createReplayState(tickEvents), { type: "START" });
    state = replayReducer(state, { type: "TICK", deltaMs: 12_000 });
    const completed = replayReducer(state, { type: "TICK", deltaMs: 1_000 });
    const afterResume = replayReducer(completed, { type: "RESUME" });

    expect(completed.status).toBe("complete");
    expect(completed.currentIndex).toBe(2);
    expect(completed.virtualTime).toBe(Date.parse("2026-09-02T00:00:12Z"));
    expect(completed.appliedEvents).toHaveLength(3);
    expect(afterResume).toEqual(completed);
  });

  it("ignores ticks while idle, paused, or complete and ignores negative ticks", () => {
    const initial = createReplayState(events);
    const idleTick = replayReducer(initial, { type: "TICK", deltaMs: 1_000 });
    const started = replayReducer(initial, { type: "START" });
    const paused = replayReducer(replayReducer(started, { type: "PAUSE" }), {
      type: "TICK",
      deltaMs: 1_000,
    });
    const negative = replayReducer(started, { type: "TICK", deltaMs: -1 });
    const complete = replayReducer(
      replayReducer(replayReducer(started, { type: "TICK", deltaMs: 1_000_000 }), {
        type: "TICK",
        deltaMs: 1_000_000,
      }),
      { type: "TICK", deltaMs: 1_000_000 },
    );
    const completeTick = replayReducer(complete, { type: "TICK", deltaMs: 1_000 });

    expect(idleTick).toEqual(initial);
    expect(paused).toEqual(replayReducer(started, { type: "PAUSE" }));
    expect(negative).toEqual(started);
    expect(complete.status).toBe("complete");
    expect(completeTick).toEqual(complete);
  });

  it("returns the prior state for malformed actions and invalid speeds", () => {
    const initial = createReplayState(events);
    const malformedActions = [
      null,
      {},
      { type: "UNKNOWN" },
      { type: "SET_SPEED" },
      { type: "SET_SPEED", speed: 3 },
      { type: "SET_SPEED", speed: "fast" },
    ] as unknown as ReplayAction[];

    for (const action of malformedActions) {
      expect(() => replayReducer(initial, action)).not.toThrow();
      expect(replayReducer(initial, action)).toBe(initial);
    }
  });

  it("returns the prior state for zero and non-finite ticks", () => {
    const started = replayReducer(createReplayState(events), { type: "START" });

    for (const deltaMs of [0, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(replayReducer(started, { type: "TICK", deltaMs })).toBe(started);
    }
  });

  it("scales advancement by speed while preserving event order", () => {
    const tickEvents = [
      event("event-1", "2026-09-02T00:00:00Z"),
      event("event-2", "2026-09-02T00:00:05Z"),
      event("event-3", "2026-09-02T00:00:12Z"),
    ];
    let oneX = replayReducer(createReplayState(tickEvents, { speed: 1 }), { type: "START" });
    let fourX = replayReducer(createReplayState(tickEvents, { speed: 4 }), { type: "START" });

    fourX = replayReducer(fourX, { type: "TICK", deltaMs: 3_000 });
    for (let tick = 0; tick < 4; tick += 1) {
      oneX = replayReducer(oneX, { type: "TICK", deltaMs: 3_000 });
    }

    expect(fourX.status).toBe("complete");
    expect(fourX.appliedEvents.map(({ event_id }) => event_id)).toEqual(
      oneX.appliedEvents.map(({ event_id }) => event_id),
    );
    expect(fourX.appliedEvents).toHaveLength(3);
  });

  it("produces identical replay results regardless of reduced motion", () => {
    const tickEvents = [
      event("event-1", "2026-09-02T00:00:00Z"),
      event("event-2", "2026-09-02T00:00:05Z"),
      event("event-3", "2026-09-02T00:00:12Z"),
    ];
    const actions = [
      { type: "START" as const },
      { type: "TICK" as const, deltaMs: 5_000 },
      { type: "SET_SPEED" as const, speed: 2 as const },
      { type: "TICK" as const, deltaMs: 4_000 },
    ];
    const applyActions = (reducedMotion: boolean) => actions.reduce(
      replayReducer,
      createReplayState(tickEvents, { reducedMotion }),
    );

    const animated = applyActions(false);
    const reduced = applyActions(true);

    expect(reduced.status).toBe(animated.status);
    expect(reduced.currentIndex).toBe(animated.currentIndex);
    expect(reduced.virtualTime).toBe(animated.virtualTime);
    expect(reduced.appliedEvents).toEqual(animated.appliedEvents);
  });
});
