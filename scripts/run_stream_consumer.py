"""Consume a bounded telemetry batch from local Redpanda into Bronze."""

import argparse
import json
import os
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from portflow.streaming.config import StreamingConfig
from portflow.streaming.consumer import consume_telemetry_stream, create_consumer


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-messages", type=_positive_int, required=True)
    parser.add_argument("--run-id", default="stream-run-000042")
    parser.add_argument(
        "--bronze-dir",
        type=Path,
        default=Path(os.environ.get("PORTFLOW_STREAM_BRONZE_DIR", "data/bronze-stream")),
    )
    args = parser.parse_args(argv)

    config = StreamingConfig.from_env()
    consumer = create_consumer(config)
    report = consume_telemetry_stream(
        consumer,
        topic=config.topic,
        bronze_dir=args.bronze_dir,
        run_id=args.run_id,
        batch_size=config.batch_size,
        max_messages=args.max_messages,
    )
    print(json.dumps(asdict(report), sort_keys=True))


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


if __name__ == "__main__":
    main()
