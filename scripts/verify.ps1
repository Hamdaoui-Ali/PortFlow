$ErrorActionPreference = "Stop"

python -m uv run pytest tests/unit
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
