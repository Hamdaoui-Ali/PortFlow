# PF-122 Shareable Investigation Links

## Goal

Let an operator copy the exact PortFlow view they are reviewing, including the
current route, global filters, table filters, sorting, and selected detail.

## Context

PF-120 and PF-121 made operational view state URL-backed and added recovery for
filters that are outside the published snapshot scope. The URL is already the
canonical representation of a view, but the shell gives the operator no
explicit way to share it. Operators currently have to select the browser
address bar manually, which is easy to miss when a view contains several
filters.

## Scope

PF-122 adds one compact secondary action to the existing global filter band:

- `Copy view link` reads `window.location.href` at click time;
- the full path, query string, and hash are passed to the browser Clipboard API;
- success is announced as `View link copied.`;
- an unavailable or rejected Clipboard API is announced as `Copy unavailable. Use your browser address bar.`;
- the control works on every route, including loading, stale, empty, and filter-recovery states;
- the control remains keyboard accessible and has a visible focus treatment;
- the control uses the current shell spacing and does not add a new toolbar or navigation item.

The browser address bar remains the fallback because the static site must not
request permissions, persist user data, or introduce a backend share service.

## Non-goals

- No short-link service, server-side persistence, analytics, or authentication.
- No changes to the public snapshot schema, pipeline, filters, or route format.
- No automatic clipboard write on navigation or page load.
- No toast system or global notification framework for one action.

## Interaction and accessibility

The action is a native button with the visible label `Copy view link` and a
decorative shell icon. The outcome is rendered in an `output` element; its
polite live attribute is present only after a success or failure message so
assistive technology receives feedback without adding an idle competing live
region. The output is empty while idle and uses short, actionable copy for the
failure state. The action remains usable at the existing 320px responsive
breakpoint.

## Technical design

Create a focused `ShareViewLink` component in `web/src/app/`. Its production
implementation reads the URL only inside the click handler and delegates the
Clipboard API call to a small injectable function. Tests inject deterministic
URL and clipboard functions, avoiding permissions and platform-specific
clipboard behavior. `AppShell` renders the component beside the existing filter
summary; CSS keeps the action compact, wraps its feedback, and preserves the
current mobile grid.

## Verification

- Unit tests cover the exact URL copied, success feedback, and rejected or
  unavailable clipboard behavior.
- App shell coverage confirms the action is present beside global filters.
- Existing frontend tests, typecheck, production build, performance budgets,
  Lighthouse, and the repository R2 gate remain green.
- Manual Edge verification checks a deep equipment or incident URL and confirms
  that the copied value retains its query string and hash.
