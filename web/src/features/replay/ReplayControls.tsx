import type { ReplaySpeed, ReplayStatus } from "./replayMachine";

interface ReplayControlsProps {
  status: ReplayStatus;
  speed: ReplaySpeed;
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onReset: () => void;
  onSpeedChange: (speed: ReplaySpeed) => void;
}

export function ReplayControls({
  status,
  speed,
  onStart,
  onPause,
  onResume,
  onReset,
  onSpeedChange,
}: ReplayControlsProps) {
  const primaryLabel = status === "playing" ? "Pause replay" : status === "paused" ? "Resume replay" : "Start replay";
  const primaryAction = status === "playing" ? onPause : status === "paused" ? onResume : onStart;

  return (
    <div className="replay-controls" aria-label="Replay controls">
      <button type="button" onClick={primaryAction}>{primaryLabel}</button>
      <button type="button" onClick={onReset}>Reset replay</button>
      <label className="replay-speed-control">
        <span>Replay speed</span>
        <select value={speed} onChange={(event) => onSpeedChange(Number(event.target.value) as ReplaySpeed)}>
          <option value="0.5">0.5x</option>
          <option value="1">1x</option>
          <option value="2">2x</option>
          <option value="4">4x</option>
        </select>
      </label>
    </div>
  );
}
