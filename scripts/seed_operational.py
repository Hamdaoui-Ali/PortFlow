"""Apply local migrations and seed the deterministic operational fixture."""

import json
import os
from dataclasses import asdict
from pathlib import Path

from portflow.db.connection import get_connection
from portflow.db.migrations import apply_migrations
from portflow.seed import seed_operational


def main() -> None:
    """Seed PostgreSQL and print one machine-readable report."""
    repository_root = Path(__file__).resolve().parents[1]
    database_url = os.environ.get("PORTFLOW_DATABASE_URL")
    with get_connection(database_url) as connection:
        apply_migrations(connection, repository_root / "db" / "migrations")
        report = seed_operational(connection, seed=42)
    print(json.dumps(asdict(report), sort_keys=True))


if __name__ == "__main__":
    main()
