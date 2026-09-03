# PF-021 Live Demo Interface Design

## Goal

Build a dedicated PortFlow Live Demo page that lets visitors control a clearly disclosed browser simulation, follow its event activity, and understand changing operational KPIs without implying live data or a runtime backend.

## Product outcome

Visitors can start, pause, resume, reset, and change the speed of a deterministic replay. They can see which equipment event is active, how far the replay has progressed, and how the derived availability KPIs change. Keyboard and reduced-motion users receive the same logical experience.

## Scope

PF-021 includes:

- a `#live-demo` route rendered by the existing application shell;
- a `LiveDemoPage` feature and focused replay presentation components;
- the minimal snapshot wiring needed to pass `event_replay` and overview context to the page;
- accessible controls for Start, Pause/Resume, Reset, and speed;
- an event activity feed and changing KPI presentation;
- persistent simulation disclosure and honest absent, empty, malformed, and unavailable states;
- responsive styles and associated unit/component tests.

PF-021 does not add a backend, polling, analytics, new snapshot contracts, live operational claims, global replay context, or unrelated redesign work.

## Architecture

The existing `replayMachine` remains the pure state-machine boundary. `LiveDemoPage` owns a page-local adapter that:

1. initializes replay state from validated `SnapshotV1.event_replay`;
2. dispatches explicit `START`, `PAUSE`, `RESUME`, `RESET`, `SET_SPEED`, and `TICK` actions;
3. schedules browser timer ticks only while the machine is `playing`;
4. clears the timer on pause, reset, completion, and unmount;
5. derives display data from the machine state and the published overview context.

Child components receive plain state and callbacks:

- `ReplayDisclosure` communicates that the experience is simulated;
- `ReplayControls` renders labeled native controls;
- `ReplayKpiStrip` renders derived KPI values;
- `ReplayActivityFeed` renders applied events in chronological order.

No child component owns replay time or duplicates event ordering logic.

## Interaction contract

- Start begins from the first event and applies the full initial timestamp group.
- Pause freezes virtual time and leaves the current event list visible.
- Resume continues from the paused virtual time.
- Reset returns to the initial replay cursor while preserving the selected speed and reduced-motion policy.
- Speed selection supports exactly `0.5x`, `1x`, `2x`, and `4x`.
- Completion displays `Replay complete` and stops timer ticks. Start can restart the replay.
- A visible status region communicates replay state and the latest applied event without repeatedly announcing the entire page.
- The activity feed is a labeled list. Each row includes event state, equipment identifier, terminal, and a human-readable UTC timestamp.
- Optional or unavailable values use existing PortFlow language such as `Unavailable`; the interface never fabricates values.

## KPI derivation

The page derives a small, documented view model from the applied replay events:

- current equipment state: the latest applied event for the selected equipment;
- available status: the latest event's `available` value;
- replay progress: applied event count over total event count;
- source overview availability: the published overview KPI, shown as context rather than rewritten as live telemetry.

The page labels changing values as simulation output. It does not claim that a replay event recomputes historical aggregate availability unless that calculation is explicitly implemented and tested from available fields.

## Accessibility and motion

- Use semantic headings, native buttons, a labeled `select`, and a labeled activity list.
- Every control has an accessible name and a visible focus state.
- Status changes are announced through a bounded `role="status"` region; the full activity list is not an unbounded live region.
- Color is supplemental and never the sole indication of equipment state.
- `prefers-reduced-motion` is read as presentation policy. It does not alter reducer actions, event ordering, virtual time, or derived values.
- The layout remains usable at narrow widths without horizontal scrolling for controls or essential status content.

## Dataset states and failure handling

- Loading uses the existing page-level snapshot loading state.
- Missing `event_replay` renders a clear "Replay dataset not published" state.
- An empty replay renders a clear "Replay has no events" state.
- The current loader omits malformed or unavailable replay data from `SnapshotV1`; that same honest not-published or unavailable state is rendered without fabricating a demo.
- Stale snapshot data keeps the existing stale notice and uses the last valid snapshot consistently.
- The page remains static and browser-local after snapshot loading.

## Testing and verification

Tests will cover:

- route selection and Live Demo navigation;
- loading, absent, empty, malformed, unavailable, and stale dataset states;
- control labels and keyboard operation;
- start, pause, resume, reset, speed, completion, and repeated actions;
- activity feed ordering and bounded status announcements;
- derived current state and progress values;
- timer cleanup on pause, reset, completion, and unmount;
- reduced-motion equivalence of logical state and event order;
- persistent simulation disclosure and absence of live-data language.

Release verification runs the full frontend suite, typecheck, production build with `VITE_BASE_PATH='/PortFlow/'`, Pages verification, and `git diff --check`.

## Non-goals

- PF-022 Data Health
- PF-023 full responsive/accessibility hardening
- a reusable global replay provider
- server-side playback or live polling
- new event fields or snapshot schema changes
- visual ideation artifacts or external design-system dependencies
