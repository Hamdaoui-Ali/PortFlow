import { describe, expect, it } from "vitest";
import type { ReplayEventV1 } from "../../data/schema";
import { createReplayState, replayReducer } from "./replayMachine";

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

  it("always restarts from the first event", () => {
    const initial = createReplayState(events);
    const started = replayReducer(initial, { type: "START" });
    const paused = replayReducer(started, { type: "PAUSE" });
    const restarted = replayReducer(paused, { type: "START" });

    expect(restarted.status).toBe("playing");
    expect(restarted.currentIndex).toBe(0);
    expect(restarted.appliedEvents).toEqual([restarted.events[0]]);
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
});
