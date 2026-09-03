# First PortFlow deployment

## Permanent-$0 prerequisites

- Keep Hamdaoui-Ali/PortFlow public and on GitHub Free.
- Do not enable paid runners, larger runners, metered add-ons, or a custom paid service.
- Recheck [the cost-evidence ledger](../product/cost-evidence.md) before publishing.

## One-time repository settings

1. Open **Settings > Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Open **Settings > Environments > github-pages** and restrict deployment branches to main.
4. Open **Settings > Branches** (or **Rules > Rulesets**) and protect main: require a pull request and the verify CI check before merge. If the account does not offer the desired rules, keep the same review and green-CI gate as a documented manual rule.

No repository secret, payment card, public API, or runtime server is required.

## First publication

1. Merge the reviewed release commit to main.
2. Open **Actions > Publish PortFlow** and confirm both build and deploy are green.
3. Open **Settings > Pages** or the workflow's github-pages environment to copy the published URL.
4. Confirm that index.html, hashed CSS and JavaScript, data/manifest.json, the versioned snapshot datasets, and brand/portflow-mark.png return HTTP 200.
5. Confirm the page says **Simulated terminal operations data** and displays equipment availability as 94.4%.

The expected project path is /PortFlow/. The Pages build fails if compiled asset or snapshot requests do not use that base path.

## Local release-equivalent check

    docker compose up -d --wait postgres
    python -m uv sync --extra dev --frozen
    npm --prefix web ci
    ./scripts/verify_r2.ps1
    docker compose down

Every command must exit 0. PostgreSQL is disposable local/CI state; it is never exposed to the browser.
The public website is static HTML, CSS, JavaScript, and committed JSON. If a pipeline stage fails,
the previous manifest and snapshot remain in place.

## Rollback

1. Identify the last known-good commit in **Actions > Publish PortFlow**.
2. Revert the faulty commit through a reviewed pull request; do not rewrite main history.
3. Merge the revert and let the workflow deploy that commit's fresh static artifact.
4. Repeat the HTTP and visible-page checks above.

If GitHub Pages becomes unavailable or its policy stops meeting the cost gate, preserve web/dist and upload that same static directory to another verified free static host.
