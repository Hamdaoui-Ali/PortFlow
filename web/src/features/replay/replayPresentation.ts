import type { OverviewV1, ReplayEventV1 } from "../../data/schema";
import type { ReplayState } from "./replayMachine";

export interface ReplayViewModel {
  currentEvent: ReplayEventV1 | null;
  progressLabel: string;
  availabilityLabel: string;
  currentStateLabel: string;
  sourceAvailabilityLabel: string;
  latestEventLabel: string;
}

const utcTimestampFormatter = new Intl.DateTimeFormat("en-US", {
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  month: "short",
  timeZone: "UTC",
  timeZoneName: "short",
  year: "numeric",
});

export function deriveReplayViewModel(state: ReplayState, overview: OverviewV1): ReplayViewModel {
  const currentEvent = state.appliedEvents.at(-1) ?? null;
  return {
    currentEvent,
    progressLabel: `${state.appliedEvents.length} of ${state.events.length} events`,
    availabilityLabel: currentEvent ? (currentEvent.available ? "Available" : "Unavailable") : "Unavailable",
    currentStateLabel: currentEvent?.state ?? "Unavailable",
    sourceAvailabilityLabel: overview.availability.value === null
      ? "Unavailable"
      : `${(overview.availability.value * 100).toFixed(1)}%`,
    latestEventLabel: currentEvent ? formatReplayEvent(currentEvent) : "No replay events applied",
  };
}

export function formatReplayTimestamp(timestamp: string): string {
  return utcTimestampFormatter.format(new Date(timestamp));
}

export function formatReplayEvent(event: ReplayEventV1): string {
  return `${event.event_id} · ${event.equipment_id} · ${event.terminal_id} · ${event.state}`;
}
