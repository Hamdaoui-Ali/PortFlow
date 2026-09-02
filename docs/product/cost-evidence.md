# PortFlow Cost Evidence

**Verified:** 2026-09-02

This ledger validates only external services required by PortFlow V1. It uses official vendor documentation and avoids assuming that today's policy is guaranteed forever.

| Service | Official URL | Billing requirement | Relevant constraint | Risk | Fallback |
|---|---|---|---|---|---|
| GitHub Free | https://docs.github.com/en/billing/get-started/how-billing-works | GitHub can be used without cost; paid plans and metered products are optional | PortFlow must not enable paid plans, paid add-ons, or metered products | Vendor policy can change | Move the Git repository to another free Git host or keep it local |
| GitHub Pages | https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits | Available from public repositories on GitHub Free | Published site and source repository: 1 GB; soft bandwidth limit: 100 GB/month; deployment timeout: 10 minutes; not permitted as free hosting for commercial SaaS | Rate limiting or policy change could interrupt the public URL | Publish the same static `web/dist` artifact with another free static host or serve it locally |
| GitHub Actions standard hosted runners | https://docs.github.com/en/actions/reference/runners/github-hosted-runners | Standard runners are free and unlimited for public repositories | Larger runners are excluded; workflows must use standard public-repository runners | Artifact storage and separate metered features have different rules | Generate snapshots and build `web/dist` locally, then publish the static artifact through another free host |
| GitHub Actions billing | https://docs.github.com/en/billing/concepts/product-billing/github-actions | Standard hosted runners are free for public repositories and for GitHub Pages | Larger runners are always charged; artifact storage allowances still apply | A workflow change could accidentally select a paid runner or retain excessive artifacts | Restrict workflows to standard `ubuntu-latest`, keep artifact retention short, and use local builds as fallback |

## Cost gate

PortFlow V1 passes the current cost gate only when all of these remain true:

- the repository is public;
- GitHub Pages is used only for the open portfolio/data-visualization project described here;
- workflows use standard GitHub-hosted runners;
- paid runners, paid plans, paid add-ons, and metered services are not enabled;
- the site and repository remain below 1 GB;
- the expected audience remains far below the 100 GB/month soft bandwidth limit;
- the build completes within 10 minutes;
- no public API, database, broker, or server process is introduced.

## Verification procedure

Recheck this ledger before the first deployment and every six months afterward. If a policy changes, stop automated publication, preserve the last generated `web/dist` artifact, and activate the documented static-host fallback.
