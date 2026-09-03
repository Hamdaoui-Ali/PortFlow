# PortFlow UI Specification

**Status:** Approved on 2026-09-02

## Visual references

- `docs/design/portflow-overview-desktop-concept.png` — primary desktop reference, native size 1600 × 960.
- `docs/design/portflow-overview-mobile-concept.png` — responsive reference, native size 852 × 1860.
- `web/public/brand/portflow-mark.png` — generated transparent brand mark.

The concept images define composition, density, typography relationships, palette, component shape, borders, icon treatment, and responsive behavior. They are not shipped as interface screenshots.

## Design direction

PortFlow is serious maritime operations software. It uses a cool, precise, airy control-tower language: a light-gray canvas, crisp white working surfaces, deep navy typography, cobalt and teal analytical accents, and tightly limited amber/red operational states.

The interface is table- and rail-driven. It avoids a generic bento dashboard, nested cards, gradients, glow, glass effects, decorative pills, photography, and marketing-page structure.

## Color tokens

| Token | Value | Use |
|---|---|---|
| `--canvas` | `#f5f7fa` | Application background |
| `--surface` | `#ffffff` | Working surfaces |
| `--ink` | `#10233f` | Primary text and icons |
| `--muted` | `#5c6b7e` | Secondary labels and timestamps |
| `--border` | `#d8e0ea` | Dividers and control borders |
| `--cobalt` | `#0867e8` | Primary data and selected navigation |
| `--teal` | `#079a98` | Healthy availability and operational state |
| `--amber` | `#f2a20c` | Warning and degraded state |
| `--critical` | `#d92332` | Critical incidents and down state |
| `--focus` | `#064fc4` | Visible keyboard focus ring |

No gradient or translucent color overlay is part of the accepted design.

## Typography

- Family: Inter Variable with `Segoe UI`, Arial, and sans-serif fallbacks.
- Page title: 28–32 px desktop, 28 px mobile; weight 700; compact line height.
- Section heading: 18–20 px; weight 700.
- KPI value: 36–42 px desktop, 34–40 px mobile; weight 700; tabular numerals.
- Body: 15–16 px; weight 400–500; line height 1.5.
- Navigation and controls: 14 px; weight 500–600; never browser-default typography.
- Table text: 14 px; tabular numerals for quantitative columns.
- Supporting metadata: 12–13 px; weight 500.

## Spacing and geometry

- Base spacing unit: 4 px.
- Major desktop gutters: 24–28 px.
- Mobile page gutters: 16 px.
- Control height: 44–48 px.
- Touch target: at least 44 × 44 px.
- Working-surface radius: 10 px.
- Control radius: 7 px.
- Dividers: 1 px solid `--border`.
- Shadows: none by default; a single very light elevation is allowed only for mobile fixed navigation.

## Container model

- Desktop: 232 px left navigation rail, a quiet header, full-width filter band, KPI rail, two-column analytical region, attention table, and bottom data-health strip.
- Mobile: single content column, compact header, two-column filters, two-column KPI rail with the fifth KPI occupying one cell, vertically stacked charts/lists, and fixed bottom navigation.
- KPI sections use dividers rather than floating cards.
- Data tables remain tables on desktop. On mobile, lower-priority columns may hide, but data must not become an unrelated card grid.

## Allowed navigation copy

1. `Overview`
2. `Equipment`
3. `Incidents`
4. `Live Demo`
5. `Data Health`

## Allowed first-viewport copy

- `PortFlow`
- `Terminal Operations Control Tower`
- `Simulated terminal operations data`
- `Updated 2 Sep 2026 · 21:40 UTC`
- `Terminal`
- `Casablanca Terminal`
- `Date range`
- `Last 24 hours`
- `Throughput`
- `1,284 moves`
- `Equipment availability`
- `94.8%`
- `Average dwell time`
- `18.6 h`
- `MTTR`
- `42 min`
- `Active incidents`
- `3`
- `Terminal throughput (moves)`
- `Equipment status distribution`
- `Equipment requiring attention`
- `Data health: All critical sources operational`

The first public vertical slice may show only the title, simulation disclosure, update timestamp, equipment availability, its definition, and an unavailable state. It must still use this visual system and must not invent additional above-the-fold copy.

## Icons

- Style: consistent outline icons, approximately 1.75 px stroke, round joins and caps.
- Default color: `--ink`; selected color: `--cobalt`; semantic state colors use the palette above.
- Required families: overview grid, equipment crane, incident warning, live-demo play rectangle, data-health pulse, information, calendar, terminal, availability check, clock, maintenance wrench, and chevron.
- Use Lucide when its metaphor and stroke style match the concept. Use a focused custom SVG only for the crane/terminal metaphor if the library equivalent is visibly wrong.
- Icons remain optically aligned to labels and never replace accessible text.

## Brand treatment

The PortFlow mark is three cobalt maritime wave strokes. Display it beside the `PortFlow` wordmark at 30–36 px visual height on desktop and mobile. The image has a transparent background and no overlay, shadow, glow, or container.

## Component families

- `AppShell`: responsive header, desktop rail, mobile bottom navigation.
- `FilterControl`: labelled select/date control with consistent 48 px height.
- `KpiRail` and `KpiItem`: divider-based metrics with icon, label, value, and semantic status.
- `ChartRegion`: open analytical surface with heading, legend, code-native chart, and text summary.
- `OperationsTable`: compact table with sorting affordance and aligned numeric columns.
- `DataHealthStrip`: low-height status rail with text and timestamp.
- `DataState`: loading, empty, stale, malformed, and unavailable messages.

## States and motion

- Selected navigation uses cobalt text, icon, a pale blue surface, and a 3 px leading indicator.
- Hover changes surface or border without shifting layout.
- Keyboard focus uses a 2 px `--focus` outline and 2 px offset.
- Charts may reveal data over 240 ms with restrained easing.
- Event replay may update charts and feeds, but `prefers-reduced-motion` removes animated transitions.
- Status is always communicated by text and shape as well as color.

## Responsive rules

- Desktop rail appears at 900 px and wider.
- Mobile bottom navigation appears below 900 px.
- At 600 px and below, content uses 16 px gutters and chart labels reduce without becoming unreadable.
- Filter controls remain side by side while each can retain a 44 px target; they stack only below 360 px.
- No horizontal page overflow is allowed.
- The fixed mobile navigation must not obscure the final content; reserve its height in page padding.

## First-slice acceptance

- The rendered desktop and mobile pages preserve the reference hierarchy and palette.
- The simulation disclosure is visible without interaction.
- The availability value or `Unavailable` is the primary data focus.
- The KPI definition and update time remain readable.
- Loading and error states use the same shell rather than a blank page.
- All interactive elements are reachable by keyboard and meet the 44 px target rule.
