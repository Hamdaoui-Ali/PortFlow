import { z } from "zod";

const utcDateTime = z.iso.datetime({ offset: true });
const relativeJsonPath = z
  .string()
  .regex(/^(?!\/)(?!.*\.\.)(?:[A-Za-z0-9._-]+\/)*[A-Za-z0-9._-]+\.json$/);

export const manifestSchema = z
  .object({
    datasets: z.object({
      overview: z.object({
        path: relativeJsonPath,
        sha256: z.string().regex(/^[a-f0-9]{64}$/),
      }),
    }),
    generated_at: utcDateTime,
    quality_status: z.literal("PASS"),
    record_counts: z.object({ telemetry: z.number().int().nonnegative() }),
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
    schema_version: z.literal(1),
    terminal_id: z.string().regex(/^TM-\d{3}$/),
  })
  .strict();

export type ManifestV1 = z.infer<typeof manifestSchema>;
export type OverviewV1 = z.infer<typeof overviewSchema>;

export interface SnapshotV1 {
  manifest: ManifestV1;
  overview: OverviewV1;
}
