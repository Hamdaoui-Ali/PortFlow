"""Safe offline command-line entry point for BigQuery portability artifacts."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Never

from .runner import RunSpec, run_bundle, verify_bundle

_SAFE_REASON_CODES = frozenset(
    {
        "artifact_path_invalid",
        "cloud_execution_not_offline",
        "dbt_reference_failed",
        "fixture_hash_mismatch",
        "fixture_missing",
        "forbidden_duckdb_construct",
        "gold_output_missing",
        "implicit_select_star",
        "invalid_dataset",
        "invalid_google_sql",
        "invalid_project_id",
        "manifest_invalid",
        "missing_output_field",
        "query_hash_mismatch",
        "result_hash_mismatch",
        "run_failed",
        "schema_hash_mismatch",
        "unrendered_template",
        "verification_failed",
    }
)


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        del message
        self.print_usage()
        print("invalid command-line arguments")
        raise SystemExit(2)


def _safe_reason_code(error: BaseException, fallback: str) -> str:
    try:
        instance_dict = object.__getattribute__(error, "__dict__")
    except (AttributeError, TypeError):
        instance_dict = None
    if type(instance_dict) is dict and "reason_code" in instance_dict:
        reason_code = instance_dict["reason_code"]
    else:
        reason_code = None
        for error_type in type.mro(type(error)):
            class_dict = type.__getattribute__(error_type, "__dict__")
            if "reason_code" in class_dict:
                reason_code = class_dict["reason_code"]
                break
    if type(reason_code) is str and reason_code in _SAFE_REASON_CODES:
        return reason_code
    return fallback


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(prog="python -m labs.portflow_bigquery")
    commands = parser.add_subparsers(dest="command")

    run = commands.add_parser("run", help="build and verify a local artifact bundle")
    run.add_argument("--output", type=Path, default=Path(".portability/bigquery"))
    run.add_argument("--project-id", default="demo-project")
    run.add_argument("--dataset", default="portflow")
    run.add_argument("--seed", type=int, default=42)

    verify = commands.add_parser("verify", help="verify a local artifact bundle")
    verify.add_argument(
        "--manifest",
        type=Path,
        default=Path(".portability/bigquery/manifest.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    if args.command == "run":
        try:
            run_bundle(
                RunSpec(
                    repository_root=Path.cwd(),
                    output_root=args.output,
                    project_id=args.project_id,
                    dataset=args.dataset,
                    seed=args.seed,
                )
            )
        except (OSError, ValueError) as error:
            reason_code = _safe_reason_code(error, "run_failed")
            print(f"portability run failed: {reason_code}")
            return 1
        print("portability bundle verified")
        return 0
    if args.command == "verify":
        try:
            verify_bundle(args.manifest, repository_root=Path.cwd())
        except (OSError, ValueError, json.JSONDecodeError) as error:
            reason_code = _safe_reason_code(error, "verification_failed")
            print(f"portability verification failed: {reason_code}")
            return 1
        print("portability bundle verified")
        return 0
    parser.print_help()
    return 2
