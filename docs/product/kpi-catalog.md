# PortFlow KPI Catalog

These definitions describe the metrics shown on the Operations Overview. All
values use the validated public snapshot and its published source period.

| KPI | Formula | Grain | Time boundary | Exclusions | Zero denominator |
|---|---|---|---|---|---|
| Throughput | Count of completed movement records. | One completed movement. | Published snapshot period. | Cancelled or incomplete movements. | `0 moves` |
| Equipment availability | Available intervals divided by scheduled intervals. | One equipment observation interval. | Published snapshot period. | Invalid and quarantined observations. | `Unavailable` |
| Average dwell time | Total completed stay minutes divided by completed movements. | One completed movement. | Published snapshot period. | Incomplete movements and invalid durations. | `Unavailable` |
| MTTR | Total repair minutes divided by qualifying resolved failures. | One resolved failure. | Failures resolved within the published snapshot period. | Unresolved incidents and non-failure events. | `Unavailable` |
| Active incidents | Count of incidents open at the snapshot period end. | One incident. | Snapshot period end timestamp. | Resolved incidents. | `0` |

The UI catalog is maintained in `web/src/content/kpis.ts`. The rendered
“About” disclosures expose the same formula, grain, time boundary, exclusions,
and zero-denominator behavior without changing the displayed KPI value.
