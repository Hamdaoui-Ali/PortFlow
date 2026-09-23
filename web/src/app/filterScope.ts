import type { SnapshotV1 } from "../data/schema";

const terminalLabels: Record<string, string> = {
  "TM-001": "Casablanca Terminal",
  "TM-002": "Tangier Terminal",
};

const utcDateTimeFormatter = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "UTC",
});

export interface SnapshotFilterScope {
  terminalLabel: string;
  periodLabel: string;
}

export function deriveSnapshotFilterScope(snapshot: SnapshotV1): SnapshotFilterScope {
  return {
    terminalLabel: terminalLabels[snapshot.overview.terminal_id] ?? snapshot.overview.terminal_id,
    periodLabel: formatSnapshotPeriod(
      snapshot.manifest.source_period_start,
      snapshot.manifest.source_period_end,
    ),
  };
}

export function formatSnapshotPeriod(start: string, end: string): string {
  const startLabel = utcDateTimeFormatter.format(new Date(start));
  const endLabel = utcDateTimeFormatter.format(new Date(end));
  const [startDate, startTime] = startLabel.split(", ");
  const [endDate, endTime] = endLabel.split(", ");

  if (startDate === endDate) {
    return `${startDate}, ${startTime}–${endTime} UTC`;
  }

  return `${startLabel} – ${endLabel} UTC`;
}
