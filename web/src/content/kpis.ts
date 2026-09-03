export const KPI_IDS = [
  "throughput",
  "availability",
  "average-dwell",
  "mttr",
  "active-incidents",
] as const;

export type KpiId = (typeof KPI_IDS)[number];

export interface KpiDefinition {
  label: string;
  formula: string;
  grain: string;
  timeBoundary: string;
  exclusions: string;
  zeroDenominator: string;
}

export const KPI_DEFINITIONS: Record<KpiId, KpiDefinition> = {
  throughput: {
    label: "Throughput",
    formula: "Count of completed movement records.",
    grain: "One completed movement.",
    timeBoundary: "The published snapshot period.",
    exclusions: "Cancelled or incomplete movements are excluded.",
    zeroDenominator: "Zero completed movements displays as 0 moves.",
  },
  availability: {
    label: "Equipment availability",
    formula: "Available intervals divided by scheduled intervals.",
    grain: "One equipment observation interval.",
    timeBoundary: "The published snapshot period.",
    exclusions: "Invalid and quarantined observations are excluded.",
    zeroDenominator: "No scheduled intervals displays as Unavailable.",
  },
  "average-dwell": {
    label: "Average dwell time",
    formula: "Total completed stay minutes divided by completed movements.",
    grain: "One completed movement.",
    timeBoundary: "The published snapshot period.",
    exclusions: "Incomplete movements and invalid durations are excluded.",
    zeroDenominator: "No completed movements displays as Unavailable.",
  },
  mttr: {
    label: "MTTR",
    formula: "Total repair minutes divided by qualifying resolved failures.",
    grain: "One resolved failure.",
    timeBoundary: "Failures resolved within the published snapshot period.",
    exclusions: "Unresolved incidents and non-failure events are excluded.",
    zeroDenominator: "No qualifying resolved failures displays as Unavailable.",
  },
  "active-incidents": {
    label: "Active incidents",
    formula: "Count of incidents open at the snapshot period end.",
    grain: "One incident.",
    timeBoundary: "The snapshot period end timestamp.",
    exclusions: "Resolved incidents are excluded.",
    zeroDenominator: "No open incidents displays as 0.",
  },
};
