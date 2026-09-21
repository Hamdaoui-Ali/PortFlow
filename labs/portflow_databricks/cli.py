"""Bounded command-line entry point for the PF-107 offline handoff."""

import argparse
from collections.abc import Sequence
from pathlib import Path

import duckdb
import polars as pl

from .runner import RunSpec, run_bundle, verify_bundle

_SAFE_REASON_CODES = frozenset(
    {
        "run_failed",
        "notebook_hash_mismatch",
        "schema_hash_mismatch",
        "fixture_hash_mismatch",
        "result_hash_mismatch",
        "artifact_path_invalid",
        "notebook_contract_invalid",
        "manifest_invalid",
        "cloud_execution_not_offline",
    }
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m labs.portflow_databricks")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="generate and verify an offline handoff bundle")
    run.add_argument("--output", type=Path, default=Path(".databricks/pf107"))
    run.add_argument("--seed", type=int, default=42)

    verify = commands.add_parser("verify", help="verify an existing handoff manifest")
    verify.add_argument("--manifest", type=Path, required=True)
    return parser


def _reason_code(error: BaseException) -> str:
    candidate = getattr(error, "reason_code", "run_failed")
    return candidate if candidate in _SAFE_REASON_CODES else "run_failed"


def main(argv: Sequence[str] | None = None) -> int:
    """Run one bounded command and return a shell-friendly status code."""
    try:
        arguments = _parser().parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2

    try:
        if arguments.command == "run":
            run_bundle(
                RunSpec(
                    repository_root=Path.cwd(),
                    output_root=arguments.output,
                    seed=arguments.seed,
                )
            )
        else:
            verify_bundle(arguments.manifest, repository_root=Path.cwd())
    except (
        OSError,
        ValueError,
        duckdb.Error,
        pl.exceptions.PolarsError,
    ) as error:
        print(f"databricks verification failed: {_reason_code(error)}")
        return 1

    print("databricks handoff bundle verified")
    return 0
