import type { ReplayEventV1 } from "../../data/schema";

export type ReplayEvent = ReplayEventV1;

export interface HourlyAvailability {
  available: number;
  label: string;
  total: number;
  value: number;
}

export function groupHourlyAvailability(events: ReplayEvent[]): HourlyAvailability[] {
  const buckets = new Map<string, { available: number; total: number }>();

  for (const event of events) {
    const instant = new Date(event.event_timestamp);
    const key = instant.toISOString().slice(0, 13);
    const bucket = buckets.get(key) ?? { available: 0, total: 0 };
    bucket.total += 1;
    if (event.available) bucket.available += 1;
    buckets.set(key, bucket);
  }

  return [...buckets.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, bucket]) => ({
      ...bucket,
      label: `${key.slice(11, 13)}:00`,
      value: bucket.available / bucket.total,
    }));
}
