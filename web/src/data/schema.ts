import { z } from "zod";

const utcDateTime = z.iso.datetime({ offset: true });
const relativeJsonPath = z
  .string()
  .regex(/^(?!\/)(?!.*\.\.)(?:[A-Za-z0-9._-]+\/)*[A-Za-z0-9._-]+\.json$/);

const datasetEntry = z
  .object({
    path: relativeJsonPath,
    sha256: z.string().regex(/^[a-f0-9]{64}$/),
  })
  .strict();

export const manifestSchema = z
  .object({
    datasets: z
      .object({
        overview: datasetEntry,
        equipment: datasetEntry.optional(),
        incidents: datasetEntry.optional(),
        event_replay: datasetEntry.optional(),
        quality: datasetEntry.optional(),
      })
      .strict(),
    generated_at: utcDateTime,
    quality_status: z.literal("PASS"),
    record_counts: z
      .object({
        telemetry: z.number().int().nonnegative(),
        equipment: z.number().int().nonnegative().optional(),
        incidents: z.number().int().nonnegative().optional(),
        event_replay: z.number().int().nonnegative().optional(),
        quality: z.number().int().nonnegative().optional(),
      })
      .strict(),
    schema_version: z.literal(1),
    snapshot_id: z.string().min(1),
    source_period_end: utcDateTime,
    source_period_start: utcDateTime,
  })
  .strict();

const availabilitySchema = z
  .object({
    available_intervals: z.number().int().nonnegative(),
    scheduled_intervals: z.number().int().nonnegative(),
    value: z.number().min(0).max(1).nullable(),
  })
  .superRefine((availability, context) => {
    if (availability.available_intervals > availability.scheduled_intervals) {
      context.addIssue({
        code: "custom",
        message: "available intervals cannot exceed scheduled intervals",
      });
    }
    if (availability.scheduled_intervals === 0 && availability.value !== null) {
      context.addIssue({ code: "custom", message: "empty periods require a null value" });
    }
    if (availability.scheduled_intervals > 0 && availability.value === null) {
      context.addIssue({ code: "custom", message: "scheduled periods require a value" });
    }
    if (availability.value !== null && availability.scheduled_intervals > 0) {
      const expected = availability.available_intervals / availability.scheduled_intervals;
      if (Math.abs(availability.value - expected) > Number.EPSILON * 8) {
        context.addIssue({ code: "custom", message: "value must match the interval counts" });
      }
    }
  });

export const overviewSchema = z
  .object({
    availability: availabilitySchema,
    available_intervals: z.number().int().nonnegative().optional(),
    scheduled_intervals: z.number().int().nonnegative().optional(),
    active_intervals: z.number().int().nonnegative().optional(),
    utilization: z.number().min(0).max(1).nullable().optional(),
    throughput: z.number().int().nonnegative().optional(),
    average_dwell_minutes: z.number().nonnegative().nullable().optional(),
    mttr_minutes: z.number().nonnegative().nullable().optional(),
    mtbf_hours: z.number().nonnegative().nullable().optional(),
    resolved_incident_count: z.number().int().nonnegative().optional(),
    repair_minutes: z.number().nonnegative().optional(),
    qualifying_failure_count: z.number().int().nonnegative().optional(),
    operating_hours: z.number().nonnegative().optional(),
    active_incidents: z.number().int().nonnegative().optional(),
    critical_alarms: z.number().int().nonnegative().optional(),
    source_period_start: utcDateTime.optional(),
    source_period_end: utcDateTime.optional(),
    schema_version: z.literal(1),
    terminal_id: z.string().regex(/^TM-\d{3}$/),
  })
  .strict();

export const replayEventSchema = z
  .object({
    available: z.boolean(),
    equipment_id: z.string().min(1),
    event_id: z.string().min(1),
    event_timestamp: utcDateTime,
    state: z.string().min(1),
    terminal_id: z.string().regex(/^TM-\d{3}$/),
  })
  .strict();

export const replaySchema = z.array(replayEventSchema);

export const equipmentRecordSchema = z
  .object({
    alarm_count: z.number().int().nonnegative(),
    availability: z.number().min(0).max(1).nullable(),
    available: z.boolean(),
    current_state: z.string().min(1),
    downtime_minutes: z.number().nonnegative().nullable(),
    equipment_id: z.string().min(1),
    mtbf_hours: z.number().nonnegative().nullable(),
    mttr_minutes: z.number().nonnegative().nullable(),
    terminal_id: z.string().regex(/^TM-\d{3}$/),
    utilization: z.number().min(0).max(1).nullable(),
  })
  .strict();

export const equipmentSchema = z.array(equipmentRecordSchema);

export type ManifestV1 = z.infer<typeof manifestSchema>;
export type OverviewV1 = z.infer<typeof overviewSchema>;
export type ReplayEventV1 = z.infer<typeof replayEventSchema>;
export type EquipmentRecordV1 = z.infer<typeof equipmentRecordSchema>;

export type EquipmentDatasetState =
  | { status: "absent" }
  | { status: "ready"; records: EquipmentRecordV1[] }
  | { status: "unavailable" }
  | { status: "malformed" }
  | { status: "empty" };

export interface SnapshotV1 {
  manifest: ManifestV1;
  overview: OverviewV1;
  event_replay?: ReplayEventV1[];
  equipment?: EquipmentDatasetState;
}
