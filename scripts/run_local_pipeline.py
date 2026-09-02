"""Run the trusted local pipeline and print its public manifest path."""

import os
from pathlib import Path

from portflow.pipeline import run_local_pipeline


def main() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    database_url = os.environ.get(
        "PORTFLOW_DATABASE_URL",
        "postgresql://portflow:portflow@localhost:5433/portflow",
    )
    manifest_path = run_local_pipeline(
        database_url=database_url,
        output_dir=repository_root / "web" / "public" / "data",
    )
    print(manifest_path)


if __name__ == "__main__":
    main()
