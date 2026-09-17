import json
from datetime import UTC, datetime

import pytest

from portflow.domain.models import EquipmentState, TelemetryEvent
from portflow.streaming.codec import (
    StreamValidationError,
    decode_telemetry_event,
    encode_telemetry_event,
    telemetry_headers,
)


def valid_event() -> TelemetryEvent:
    return TelemetryEvent(
        event_id="evt-000042-000001",
        schema_version=1,
        equipment_id="QC-001",
        terminal_id="TM-001",
        event_timestamp=datetime(2026, 9, 2, tzinfo=UTC),
        ingestion_timestamp=datetime(2026, 9, 2, 0, 0, 2, tzinfo=UTC),
        state=EquipmentState.ACTIVE,
        available=True,
        load_percent=50.0,
        temperature_c=55.0,
    )


def test_encoding_is_canonical_and_round_trips() -> None:
    event = valid_event()

    encoded = encode_telemetry_event(event)

    assert encoded == encode_telemetry_event(event)
    assert decode_telemetry_event(encoded, telemetry_headers()) == event
    assert list(json.loads(encoded)) == sorted(json.loads(encoded))


def test_decoder_rejects_bad_payload_and_headers() -> None:
    with pytest.raises(StreamValidationError, match="headers"):
        decode_telemetry_event(b"{}", (("portflow-event-type", b"wrong"),))

    with pytest.raises(StreamValidationError, match="UTF-8"):
        decode_telemetry_event(b"\xff", telemetry_headers())

    with pytest.raises(StreamValidationError, match="TelemetryEvent"):
        decode_telemetry_event(b'{"event_id":"bad"}', telemetry_headers())


@pytest.mark.parametrize(
    "payload, headers",
    [
        (None, telemetry_headers()),
        (b"[]", telemetry_headers()),
        (b"{", telemetry_headers()),
        (encode_telemetry_event(valid_event()), (("portflow-event-type", b"telemetry"),)),
        (
            encode_telemetry_event(valid_event()),
            telemetry_headers() + (("portflow-event-type", b"telemetry"),),
        ),
    ],
)
def test_decoder_rejects_missing_or_malformed_records(
    payload: bytes | None,
    headers: tuple[tuple[str, bytes | None], ...],
) -> None:
    with pytest.raises(StreamValidationError):
        decode_telemetry_event(payload, headers)
