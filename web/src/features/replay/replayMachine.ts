import type { ReplayEventV1 } from "../../data/schema";

export type ReplayStatus = "idle" | "playing" | "paused" | "complete";
export type ReplaySpeed = 0.5 | 1 | 2 | 4;

function isReplaySpeed(speed: unknown): speed is ReplaySpeed {
  return speed === 0.5 || speed === 1 || speed === 2 || speed === 4;
}

export interface ReplayState {
  status: ReplayStatus;
  events: ReplayEventV1[];
  currentIndex: number;
  virtualTime: number | null;
  appliedEvents: ReplayEventV1[];
  speed: ReplaySpeed;
  reducedMotion: boolean;
}

export type ReplayAction =
  | { type: "START" }
  | { type: "PAUSE" }
  | { type: "RESUME" }
  | { type: "RESET" }
  | { type: "SET_SPEED"; speed: ReplaySpeed }
  | { type: "TICK"; deltaMs: number };

export function createReplayState(
  events: ReplayEventV1[],
  options: { speed?: ReplaySpeed; reducedMotion?: boolean } = {},
): ReplayState {
  const normalizedEvents = events
    .map((event, originalIndex) => ({ event, originalIndex }))
    .sort((left, right) => {
      const timestampDifference =
        Date.parse(left.event.event_timestamp) - Date.parse(right.event.event_timestamp);
      return timestampDifference || left.originalIndex - right.originalIndex;
    })
    .map(({ event }) => event);

  return {
    status: normalizedEvents.length === 0 ? "complete" : "idle",
    events: normalizedEvents,
    currentIndex: -1,
    virtualTime: normalizedEvents.length === 0
      ? null
      : Date.parse(normalizedEvents[0].event_timestamp),
    appliedEvents: [],
    speed: isReplaySpeed(options.speed) ? options.speed : 1,
    reducedMotion: options.reducedMotion ?? false,
  };
}

export function replayReducer(state: ReplayState, action: ReplayAction): ReplayState {
  if (action === null || typeof action !== "object" || !("type" in action)) {
    return state;
  }

  switch (action.type) {
    case "START":
      if (state.events.length === 0) {
        return state.status === "complete" ? state : { ...state, status: "complete" };
      }
      return {
        ...state,
        status: state.events.length === 1 ? "complete" : "playing",
        currentIndex: 0,
        virtualTime: Date.parse(state.events[0].event_timestamp),
        appliedEvents: [state.events[0]],
      };
    case "PAUSE":
      return state.status === "playing" ? { ...state, status: "paused" } : state;
    case "RESUME":
      return state.status === "paused" ? { ...state, status: "playing" } : state;
    case "RESET":
      return createReplayState(state.events, {
        speed: state.speed,
        reducedMotion: state.reducedMotion,
      });
    case "SET_SPEED":
      if (!isReplaySpeed(action.speed)) {
        return state;
      }
      return { ...state, speed: action.speed };
    case "TICK":
      if (state.status !== "playing" || !Number.isFinite(action.deltaMs) || action.deltaMs <= 0) {
        return state;
      }

      if (state.virtualTime === null) {
        return state;
      }

      const nextVirtualTime = state.virtualTime + action.deltaMs * state.speed;
      const reachedEvents = state.events.slice(state.currentIndex + 1).filter(
        (event) => Date.parse(event.event_timestamp) <= nextVirtualTime,
      );

      if (reachedEvents.length === 0) {
        return { ...state, virtualTime: nextVirtualTime };
      }

      const appliedEvents = [...state.appliedEvents, ...reachedEvents];
      const currentIndex = state.currentIndex + reachedEvents.length;
      const reachedFinalEvent = currentIndex === state.events.length - 1;

      return {
        ...state,
        status: reachedFinalEvent ? "complete" : "playing",
        currentIndex,
        virtualTime: reachedFinalEvent
          ? Date.parse(state.events[currentIndex].event_timestamp)
          : nextVirtualTime,
        appliedEvents,
      };
    default:
      return state;
  }
}
