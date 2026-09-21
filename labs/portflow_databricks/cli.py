"""Bounded command-line entry point for the PF-107 offline handoff."""

import argparse
from collections.abc import Sequence
from pathlib import Path

import duckdb
import polars as pl

from .comparison import ComparisonSpec, ComparisonVerificationError, compare_result
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
        "handoff_invalid",
        "cloud_result_invalid",
        "cloud_result_hash_mismatch",
        "comparison_invalid",
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

    compare = commands.add_parser("compare", help="compare a supplied Gold result with PF-107")
    compare.add_argument(
        "--handoff-manifest",
        type=Path,
        default=Path(".databricks/pf107/manifest.json"),
    )
    compare.add_argument(
        "--cloud-result",
        type=Path,
        default=Path(".databricks/pf108/cloud-result.json"),
    )
    compare.add_argument(
        "--output",
        type=Path,
        default=Path(".databricks/pf108/comparison.json"),
    )
    return parser


def _reason_code(error: BaseException, fallback: str = "run_failed") -> str:
    try:
        candidate = BaseException.__getattribute__(error, "reason_code")
    except BaseException:
        return fallback
    if type(candidate) is str and candidate in _SAFE_REASON_CODES:
        return candidate
    return fallback


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
        elif arguments.command == "verify":
            verify_bundle(arguments.manifest, repository_root=Path.cwd())
        else:
            report = compare_result(
                ComparisonSpec(
                    repository_root=Path.cwd(),
                    handoff_manifest=arguments.handoff_manifest,
                    cloud_result=arguments.cloud_result,
                    output_path=arguments.output,
                )
            )
            comparison = report.get("comparison")
            if not isinstance(comparison, dict):
                raise ComparisonVerificationError("comparison_invalid")
            status = comparison.get("status")
            reason_code = comparison.get("reason_code")
            if status == "match" and reason_code is None:
                print("databricks comparison matched")
                return 0
            if status == "mismatch" and reason_code == "result_hash_mismatch":
                print("databricks comparison mismatch: result_hash_mismatch")
                return 1
            raise ComparisonVerificationError("comparison_invalid")
    except (
        OSError,
        ValueError,
        duckdb.Error,
        pl.exceptions.PolarsError,
    ) as error:
        if arguments.command == "compare":
            print(f"databricks comparison failed: {_reason_code(error, 'comparison_invalid')}")
        else:
            print(f"databricks verification failed: {_reason_code(error)}")
        return 1

    print("databricks handoff bundle verified")
    return 0
