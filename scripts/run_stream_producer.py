"""Publish a bounded deterministic telemetry batch to local Redpanda."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict

from portflow.seed import EQUIPMENT_ID, FIXTURE_START, TERMINAL_ID
from portflow.simulator.equipment import generate_telemetry
from portflow.streaming.config import StreamingConfig
from portflow.streaming.producer import create_producer, publish_telemetry_events


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=_non_negative_int, default=42)
    parser.add_argument("--count", type=_non_negative_int, default=288)
    args = parser.parse_args(argv)

    config = StreamingConfig.from_env()
    events = generate_telemetry(
        seed=args.seed,
        equipment_id=EQUIPMENT_ID,
        terminal_id=TERMINAL_ID,
        count=args.count,
        start_at=FIXTURE_START,
    )
    producer = create_producer(config)
    report = publish_telemetry_events(events, producer=producer, topic=config.topic)
    print(json.dumps(asdict(report), sort_keys=True))


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


if __name__ == "__main__":
    main()
