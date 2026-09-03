"""Versioned domain models shared by simulation and analytics."""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EquipmentState(StrEnum):
    """Operational state emitted by the equipment simulator."""

    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    WARNING = "WARNING"
    UNAVAILABLE = "UNAVAILABLE"
    MAINTENANCE = "MAINTENANCE"


class TelemetryEvent(BaseModel):
    """Version-one equipment telemetry contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(pattern=r"^evt-\d{6}-\d{6}$")
    schema_version: int = Field(default=1, ge=1, le=1)
    equipment_id: str = Field(pattern=r"^[A-Z]{2,4}-\d{3}$")
    terminal_id: str = Field(pattern=r"^TM-\d{3}$")
    event_timestamp: datetime
    ingestion_timestamp: datetime
    state: EquipmentState
    available: bool
    load_percent: float = Field(ge=0.0, le=100.0)
    temperature_c: float = Field(ge=-20.0, le=150.0)

    @field_validator("event_timestamp", "ingestion_timestamp")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        """Reject naive or non-UTC timestamps at the contract boundary."""
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("timestamp must use UTC")
        return value

    @model_validator(mode="after")
    def require_consistent_availability(self) -> Self:
        """Prevent state and availability from contradicting each other."""
        unavailable_states = {EquipmentState.UNAVAILABLE, EquipmentState.MAINTENANCE}
        expected = self.state not in unavailable_states
        if self.available is not expected:
            raise ValueError(f"available must be {expected} when state is {self.state.value}")
        return self
