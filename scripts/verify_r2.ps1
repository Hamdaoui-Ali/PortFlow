$ErrorActionPreference = "Stop"

$previousDatabaseUrl = $env:PORTFLOW_DATABASE_URL
$hadDatabaseUrl = Test-Path Env:PORTFLOW_DATABASE_URL
$previousDatabasePassword = $env:PORTFLOW_POSTGRES_PASSWORD
$hadDatabasePassword = Test-Path Env:PORTFLOW_POSTGRES_PASSWORD

if (
    $hadDatabaseUrl -and
    (-not $hadDatabasePassword -or [string]::IsNullOrWhiteSpace($env:PORTFLOW_POSTGRES_PASSWORD))
) {
    throw "PORTFLOW_POSTGRES_PASSWORD must be set when PORTFLOW_DATABASE_URL is set."
}
if (-not $hadDatabaseUrl) {
    if (-not $hadDatabasePassword -or [string]::IsNullOrWhiteSpace($env:PORTFLOW_POSTGRES_PASSWORD)) {
        $env:PORTFLOW_POSTGRES_PASSWORD = [Guid]::NewGuid().ToString("N")
    }
    $env:PORTFLOW_DATABASE_URL = "postgresql://portflow:$($env:PORTFLOW_POSTGRES_PASSWORD)@localhost:5433/portflow"
}

$previousFailureTests = $env:PORTFLOW_FAILURE_TESTS
$hadFailureTests = Test-Path Env:PORTFLOW_FAILURE_TESTS
$env:PORTFLOW_FAILURE_TESTS = "1"

try {
    docker compose up -d --wait postgres
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Generate deterministic public snapshot"
    python -m uv run python scripts/run_local_pipeline.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Verify generated public data is committed"
    git diff --exit-code -- web/public/data
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Run Python tests"
    python -m uv run pytest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Run Ruff"
    python -m uv run ruff check .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Run mypy"
    python -m uv run mypy src
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Run frontend tests (including failure states)"
    npm --prefix web test -- --run --maxWorkers=1
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Typecheck frontend"
    npm --prefix web run typecheck
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Build frontend"
    npm --prefix web run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Check performance budgets"
    python scripts/check_budgets.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Run Lighthouse"
    npm --prefix web run lighthouse
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "Quality gate passed."
} finally {
    if ($hadDatabaseUrl) {
        $env:PORTFLOW_DATABASE_URL = $previousDatabaseUrl
    } else {
        Remove-Item Env:PORTFLOW_DATABASE_URL -ErrorAction SilentlyContinue
    }

    if ($hadDatabasePassword) {
        $env:PORTFLOW_POSTGRES_PASSWORD = $previousDatabasePassword
    } else {
        Remove-Item Env:PORTFLOW_POSTGRES_PASSWORD -ErrorAction SilentlyContinue
    }

    if ($hadFailureTests) {
        $env:PORTFLOW_FAILURE_TESTS = $previousFailureTests
    } else {
        Remove-Item Env:PORTFLOW_FAILURE_TESTS -ErrorAction SilentlyContinue
    }
}
