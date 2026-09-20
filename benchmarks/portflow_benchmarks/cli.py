"""Command-line interface for local benchmark evidence."""

import argparse
from pathlib import Path
from typing import cast

from .runner import PROFILES, run_benchmark, verify_report
from .timing import DEFAULT_REPETITIONS, DEFAULT_WARMUPS


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run reproducible PortFlow engine benchmarks.")
    commands = parser.add_subparsers(dest="command")
    run = commands.add_parser("run", help="generate a fixture and run selected engines")
    run.add_argument("--profile", choices=sorted(PROFILES), default="smoke")
    run.add_argument("--engines", default="duckdb,polars")
    run.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    run.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    run.add_argument("--report", type=Path, default=Path(".benchmarks/reports/latest.json"))
    verify = commands.add_parser("verify", help="validate a generated report")
    verify.add_argument("--report", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        try:
            report = run_benchmark(
                profile=args.profile,
                engines=args.engines.split(","),
                warmups=args.warmups,
                repetitions=args.repetitions,
                report_path=args.report,
            )
        except (OSError, ValueError):
            print("benchmark failed")
            return 2
        engines = cast(list[dict[str, object]], report["engines"])
        statuses = [engine["status"] for engine in engines]
        if all(status == "ok" for status in statuses):
            print("benchmark completed")
            return 0
        print("benchmark completed with unavailable or failed engines")
        return 1
    if args.command == "verify":
        try:
            verify_report(args.report)
        except (OSError, ValueError):
            print("report verification failed")
            return 1
        print("report verified")
        return 0
    parser.print_help()
    return 2
