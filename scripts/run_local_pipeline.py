"""Run the trusted local pipeline and print its public manifest path."""

import os
from pathlib import Path

from portflow.db.connection import DEFAULT_DATABASE_URL
from portflow.pipeline import run_local_pipeline


def main() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    database_url = os.environ.get(
        "PORTFLOW_DATABASE_URL",
        DEFAULT_DATABASE_URL,
    )
    manifest_path = run_local_pipeline(
        database_url=database_url,
        output_dir=repository_root / "web" / "public" / "data",
    )
    print(manifest_path)


if __name__ == "__main__":
    main()
