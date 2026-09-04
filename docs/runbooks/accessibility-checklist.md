# PortFlow Accessibility and Responsive Checklist

Use this checklist against the built `/PortFlow/` site before release. Record
the observation for each viewport and browser rather than relying on automated
axe checks alone.

| Check | Viewport / browser | Observation | Result | Date |
|---|---|---|---|---|
| Tab from the address bar reaches the skip link and then primary content | 320px / Chromium |  |  |  |
| Tab from the address bar reaches the skip link and then primary content | 375px / Chromium |  |  |  |
| Focus indicators remain visible on links, selects, buttons, details, and table controls | 320px / Chromium |  |  |  |
| Focus indicators remain visible on links, selects, buttons, details, and table controls | 375px / Chromium |  |  |  |
| Equipment detail back action returns focus to the relevant list context | 375px / Chromium |  |  |  |
| Incident detail back action returns focus to the relevant list context | 375px / Chromium |  |  |  |
| No page-level horizontal scroll appears | 320px / Chromium |  |  |  |
| No page-level horizontal scroll appears | 375px / Chromium |  |  |  |
| Reduced motion removes animation/transition dependence without hiding state changes | 375px / Chromium with reduced motion enabled |  |  |  |

## Completion rule

Every row must have a recorded observation and a `PASS` result. Any blocker
must be fixed or recorded against the next approved backlog task before the
release is called complete.
