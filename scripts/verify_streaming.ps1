$ErrorActionPreference = "Stop"
$previousBrokers = $env:PORTFLOW_REDPANDA_BROKERS
$hadBrokers = Test-Path Env:PORTFLOW_REDPANDA_BROKERS
$env:PORTFLOW_REDPANDA_BROKERS = "localhost:19092"
try {
    docker compose --profile streaming up -d --wait redpanda
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python -m uv run pytest tests/streaming/test_redpanda.py -m redpanda -v
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    docker compose --profile streaming down -v redpanda
    if ($hadBrokers) { $env:PORTFLOW_REDPANDA_BROKERS = $previousBrokers }
    else { Remove-Item Env:PORTFLOW_REDPANDA_BROKERS -ErrorAction SilentlyContinue }
}
