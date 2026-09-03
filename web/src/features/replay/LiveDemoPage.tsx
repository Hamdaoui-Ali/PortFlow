import { useEffect, useReducer } from "react";

import type { OverviewV1, ReplayEventV1 } from "../../data/schema";
import { createReplayState, replayReducer, type ReplaySpeed } from "./replayMachine";
import { ReplayActivityFeed } from "./ReplayActivityFeed";
import { ReplayControls } from "./ReplayControls";
import { ReplayDisclosure } from "./ReplayDisclosure";
import { ReplayKpiStrip } from "./ReplayKpiStrip";
import { deriveReplayViewModel } from "./replayPresentation";

interface LiveDemoPageProps {
  events?: ReplayEventV1[];
  overview: OverviewV1;
}

export function LiveDemoPage({ events, overview }: LiveDemoPageProps) {
  const [state, dispatch] = useReducer(
    replayReducer,
    createReplayState(events ?? [], { reducedMotion: getReducedMotionPreference() }),
  );
  const model = deriveReplayViewModel(state, overview);

  useEffect(() => {
    if (state.status !== "playing") return undefined;
    const timerId = window.setInterval(() => dispatch({ type: "TICK", deltaMs: 1_000 }), 1_000);
    return () => window.clearInterval(timerId);
  }, [state.status]);

  if (events === undefined) {
    return (
      <LiveDemoFrame>
        <div className="data-state data-state-warning" role="status">
          <h2>Replay dataset not published</h2>
          <p>This snapshot does not include browser replay events.</p>
        </div>
      </LiveDemoFrame>
    );
  }

  if (events.length === 0) {
    return (
      <LiveDemoFrame>
        <div className="data-state" role="status">
          <h2>Replay has no events</h2>
          <p>The published replay dataset contains no event records.</p>
        </div>
      </LiveDemoFrame>
    );
  }

  const statusLabel = `Replay ${state.status}`;
  const statusText = model.currentEvent ? `${statusLabel}. Latest: ${model.latestEventLabel}` : statusLabel;

  return (
    <LiveDemoFrame>
      <section className="live-demo-intro" aria-labelledby="live-demo-title">
        <p className="section-kicker">Controlled simulation</p>
        <h2 id="live-demo-title" tabIndex={-1}>Live Demo</h2>
        <p>Step through a published terminal replay and watch the selected equipment state change over time.</p>
      </section>
      <ReplayControls
        status={state.status}
        speed={state.speed}
        onStart={() => dispatch({ type: "START" })}
        onPause={() => dispatch({ type: "PAUSE" })}
        onResume={() => dispatch({ type: "RESUME" })}
        onReset={() => dispatch({ type: "RESET" })}
        onSpeedChange={(speed: ReplaySpeed) => dispatch({ type: "SET_SPEED", speed })}
      />
      <div className="replay-status" role="status" aria-live="polite">{statusText}</div>
      <ReplayKpiStrip model={model} />
      <ReplayActivityFeed events={state.appliedEvents} />
    </LiveDemoFrame>
  );
}

function LiveDemoFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="live-demo-page">
      <ReplayDisclosure />
      {children}
    </div>
  );
}

function getReducedMotionPreference(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}
