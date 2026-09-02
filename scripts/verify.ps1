$ErrorActionPreference = "Stop"

python -m uv run pytest
python -m uv run ruff check .
python -m uv run mypy src
npm --prefix web test -- --run
npm --prefix web run typecheck
npm --prefix web run build
