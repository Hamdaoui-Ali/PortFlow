# PF-020 Deterministic Replay State Machine

## Goal

Implement a pure, deterministic browser-side state machine for replaying the validated `event_replay` snapshot dataset. The machine is the stable behavior contract that PF-021 will connect to accessible controls, an activity feed, and changing KPI displays.

## Scope

PF-020 includes only:

- `web/src/features/replay/replayMachine.ts`
- `web/src/features/replay/replayMachine.test.ts`

The task does not add the Live Demo page, timers, DOM effects, animations, or new snapshot loading behavior. Those belong to PF-021 or existing data-loading code.

## State contract

The machine exposes a `ReplayState` containing:

- `status`: `idle`, `playing`, `paused`, or `complete`;
- the normalized chronological `events`;
- `currentIndex`, initialized before the first event and advanced as events are reached;
- `virtualTime`, initialized to the first event timestamp when events exist;
- `appliedEvents`, containing events reached so far;
- `speed`, one of `0.5`, `1`, `2`, or `4`;
- `reducedMotion`, a boolean policy flag.

An empty event list produces a stable complete state with no current event and no exception.

## Reducer contract

`replayReducer(state, action)` is pure and returns a new state without mutating input arrays or event objects.

Actions:

- `START`: move from `idle`, `paused`, or `complete` to the beginning of the replay and apply events at the starting virtual timestamp;
- `PAUSE`: change `playing` to `paused` without changing time or the event cursor;
- `RESUME`: change `paused` to `playing`;
- `RESET`: return to the initial state while preserving the selected speed and reduced-motion policy;
- `SET_SPEED`: update the selected speed;
- `TICK`: advance virtual time by `deltaMs × speed` while playing, apply all reached events in timestamp order, and mark complete at the final event.

Invalid or redundant actions are no-ops. Negative tick values are ignored. `START` always restarts from the first event so the control has predictable semantics.

## Time and ordering rules

- Input events are sorted by parsed epoch timestamp, with original input order as the stable tie-breaker.
- `virtualTime` is represented as an epoch-millisecond number so timezone offsets cannot change ordering.
- A tick applies every event whose timestamp is less than or equal to the resulting virtual time.
- The first event is applied when replay starts.
- The final event is applied exactly once and changes status to `complete`.
- Replay state never reads the wall clock.

## Reduced-motion behavior

Reduced motion does not change event order, timestamps, or reducer results for the same action sequence. It is exposed as state so PF-021 can choose discrete or immediate presentation without putting animation behavior into the machine.

## Testing

Tests use fixed `ReplayEventV1` fixtures and explicit actions/ticks. They verify:

- idle initialization;
- start, pause, resume, and reset;
- speed changes;
- multiple events reached in one tick;
- chronological ordering for out-of-order and offset timestamps;
- completion and no duplicate final event;
- empty input;
- negative tick handling;
- reduced-motion event-order preservation;
- immutability of the input event list.

The focused suite must pass before the implementation is committed. The full frontend suite, typecheck, production build, Pages-path verification, and diff check remain required before PF-020 is advanced.

## Non-goals

- rendering controls or charts;
- connecting timers or `requestAnimationFrame`;
- changing snapshot schemas or loaders;
- inventing live data;
- modifying overview, equipment, or incident behavior.
