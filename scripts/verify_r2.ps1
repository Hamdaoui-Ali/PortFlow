$ErrorActionPreference = "Stop"

docker compose up -d --wait postgres
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$previousDatabaseUrl = $env:PORTFLOW_DATABASE_URL
$hadDatabaseUrl = Test-Path Env:PORTFLOW_DATABASE_URL
if (-not $hadDatabaseUrl) {
    $env:PORTFLOW_DATABASE_URL = "postgresql://portflow:portflow@localhost:5433/portflow"
}

try {
    python -m uv run python scripts/run_local_pipeline.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    git diff --exit-code -- web/public/data
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python -m uv run pytest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python -m uv run ruff check .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python -m uv run mypy src
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm --prefix web test -- --run
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm --prefix web run typecheck
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm --prefix web run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    if ($hadDatabaseUrl) {
        $env:PORTFLOW_DATABASE_URL = $previousDatabaseUrl
    } else {
        Remove-Item Env:PORTFLOW_DATABASE_URL -ErrorAction SilentlyContinue
    }
}
