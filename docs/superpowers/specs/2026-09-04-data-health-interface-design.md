# PF-022 Data Health Interface Design

## Status

Approved design for implementation planning.

## Goal

Give PortFlow visitors one trustworthy, snapshot-wide place to answer whether
the published operational data is usable, current, and internally reconciled.

## Scope

PF-022 adds a read-only `#data-health` route over the existing static snapshot.
It exposes:

- snapshot ID and generated timestamp;
- derived snapshot age and the visible 24-hour stale threshold;
- pipeline and dbt test status;
- Bronze, Silver, quarantine, and rejected record counts;
- stable rejection reasons and their counts;
- the quality rules and links to methodology and source documentation.

The page is snapshot-wide and does not inherit the global terminal or date
filters. It does not add polling, a backend, new business metrics, a new
published artifact, or changes to the versioned snapshot contract.

## Architecture

The existing snapshot loader remains the single entry point for published
data. It will gain typed handling for the manifest's optional `quality`
dataset. The quality dataset follows the same explicit optional states as the
equipment and incidents datasets: absent, ready, unavailable, malformed, or
empty.

Health interpretation lives in a pure module at
`web/src/features/health/healthPresentation.ts`. It receives the manifest,
quality dataset state, and an injected `now` timestamp. It returns a complete
view model containing the status, explanation, formatted values, reconciliation
outcomes, rejection rows, and threshold copy. React components render this
view model but do not calculate business values.

The route is added to the existing `AppRoute` union and uses the Data Health
navigation item that already exists in `AppShell`.

## Status rules

The stale threshold is 24 hours after `manifest.generated_at`.

The pure health derivation returns:

### Healthy

- quality data is ready;
- `dbt_test_status` is `PASS`;
- `bronze_rows = silver_rows + quarantine_rows`;
- the sum of rejection reason counts equals `quarantine_rows`;
- snapshot age is at most 24 hours.

### Stale

The same evidence is valid, but snapshot age is greater than 24 hours.

### Invalid

Quality data is absent, unavailable, malformed, or empty; the pipeline status
does not pass; or the row counts/rejection totals contradict one another.
The view model retains the available evidence and explains the reason instead
of presenting a false healthy state.

The exact 24-hour boundary is healthy. Age is never negative; a clock earlier
than `generated_at` is presented as zero elapsed age for display.

## Data flow

```text
manifest.json ──┐
                 ├─> loadSnapshot ──> SnapshotV1 ──> deriveHealthViewModel(now)
quality.json ────┘                                      │
                                                        └─> DataHealthPage
```

The manifest remains authoritative for snapshot metadata and declared record
counts. The quality export remains authoritative for pipeline status, layer
counts, quarantine counts, and rejection reasons. The UI derives only display
labels, age, verdict, and reconciliation explanations.

## Interface structure

`DataHealthPage` follows the existing PortFlow table-and-rail language:

1. page heading and short explanation;
2. overall status with visible text and an icon;
3. freshness/count KPI rail;
4. pipeline status and reconciliation sections;
5. rejection-reasons table;
6. native `details` disclosure for rules, threshold, and documentation links.

The healthy fixture will show the current export values: `PASS`, 305 Bronze
rows, 305 Silver rows, 0 quarantined/rejected rows, and no rejection reasons.
The empty rejection state is explicit: “No rejected records.”

## Accessibility and responsive behavior

- Status meaning is communicated with text, not color alone.
- Every timestamp uses a semantic `<time dateTime>` element.
- KPI values have visible labels and use tabular numerals.
- The rejection table has a caption and semantic header cells.
- Invalid, missing, and unavailable evidence has an explanatory status region.
- The page itself is not a broad live region.
- The health layout stacks into one column on narrow screens and does not
  require horizontal scrolling.
- No animation is required; reduced motion is therefore behaviorally
  equivalent.

## Error handling

The quality dataset is optional to the operational snapshot, so its failure
must not make Overview, Equipment, Incidents, or Live Demo unavailable. Data
Health reports that quality evidence is unavailable or invalid.

If the required manifest or overview fails, the existing app-level error or
cached-snapshot behavior remains in force. When a cached snapshot is shown
after a failed reload, the existing stale notice stays above the Data Health
page and the health view still evaluates the cached snapshot's own age and
quality evidence.

## Testing and verification

Unit tests cover the pure presentation module for:

- healthy evidence;
- exact and over-threshold age;
- inconsistent layer counts;
- inconsistent rejection totals;
- rejection reason rows;
- absent, unavailable, malformed, and empty quality states.

Loader tests cover ready, absent, unavailable, malformed, and empty quality
datasets. Component and App tests cover labels, statuses, counts, rejection
rows, documentation links, route selection, active navigation, and stale
cache behavior.

Before PF-022 is marked complete, run the full frontend test suite, TypeScript
typecheck, production build with `VITE_BASE_PATH='/PortFlow/'`, Pages-path
verification, and `git diff --check`.

## Non-goals

- changing `schemas/public-snapshot-v1.json`;
- adding server-side health checks or polling;
- adding terminal/date filters to Data Health;
- changing the Python pipeline or quality export format;
- building the broader PF-023 accessibility/responsive audit;
- adding new charts, alerts, or historical health trends.
