# Performance budgets

PF-026 keeps the public PortFlow build usable on ordinary mobile connections.
The byte checks use the committed public data and the production `web/dist`
artifacts exactly as they are built in CI.

## Artifact budgets

| Gate | Limit | Measurement |
|---|---:|---|
| Public snapshot | 100,000 bytes | Every file below `web/public/data` |
| JS and CSS bundle | 400,000 bytes | Every `.js` and `.css` file below `web/dist/assets` |
| Startup payload | 400,000 bytes | `web/dist/index.html` plus its referenced local JS and CSS |

The current measured baseline is 47,057 bytes of public data, 366,310 bytes
of JS/CSS, and 224,882 bytes of startup payload. Limits are intentionally
larger than the baseline so normal copy and fixture changes have room without
allowing an unbounded regression.

## Runtime budgets

Lighthouse CI audits the built static site with a 375px mobile viewport and
three local runs. The audit server mounts `web/dist` below the configured
`VITE_BASE_PATH`, so the Pages path is tested with the same asset URLs that
production uses. The median run must satisfy:

| Metric | Limit |
|---|---:|
| Performance score | at least 0.90 |
| First Contentful Paint | 2,000 ms |
| Largest Contentful Paint | 2,500 ms |
| Total Blocking Time | 350 ms |
| Speed Index | 3,000 ms |
| Time to Interactive | 4,000 ms |

The runtime audit uses the local build only and writes reports to the ignored
`.lighthouseci/` directory. Collection and assertion are separate commands so
a failed collection cannot be mistaken for a passing budget gate. It does not
require a public URL, analytics service, or Lighthouse CI server.

## Enforcement

Run both checks from the repository root after a production build:

```powershell
py -3.12 scripts/check_budgets.py
npm --prefix web run lighthouse
```

Any exceeded byte or runtime budget returns a non-zero exit code. The same
gate is called by `scripts/verify_r2.ps1`, so pull requests and Pages builds
use identical checks.
