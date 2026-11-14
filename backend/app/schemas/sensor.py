"""Contratos del kit ESP32 HW-390 y DS18B20."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel, ConfigDict, Field, StringConstraints, field_validator,
)

SensorVariable = Literal["soil_moisture", "soil_temperature"]
QualityFlag = Literal["ok", "clamped_dry", "clamped_wet"]
ExternalId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DeviceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_id: ExternalId
    model: str | None = None


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    plot_id: UUID
    external_id: str
    model: str | None
    status: str
    installed_at: datetime | None
    created_at: datetime


class DeviceRegistered(DeviceRead):
    secret: str


class MoistureReading(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variable: Literal["soil_moisture"]
    raw_value: int = Field(strict=True, ge=0, le=4095)
    calibrated_value: float = Field(strict=True, ge=0, le=100, allow_inf_nan=False)
    unit: Literal["%"]
    quality_flag: QualityFlag = "ok"


class TemperatureReading(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variable: Literal["soil_temperature"]
    raw_value: float = Field(strict=True, ge=-10, le=70, allow_inf_nan=False)
    calibrated_value: float = Field(strict=True, ge=-10, le=70, allow_inf_nan=False)
    unit: Literal["°C"]
    quality_flag: QualityFlag = "ok"


class ReadingsCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_id: ExternalId
    observed_at: datetime | None = None
    readings: list[Annotated[
        MoistureReading | TemperatureReading, Field(discriminator="variable"),
    ]] = Field(min_length=1, max_length=2)

    @field_validator("observed_at")
    @classmethod
    def valid_observed_at(cls, value: datetime | None):
        if value is None:
            return value
        if value.utcoffset() is None:
            raise ValueError("observed_at debe incluir zona horaria.")
        value = value.astimezone(timezone.utc)
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("observed_at no puede superar la hora actual en más de 5 minutos.")
        return value

    @field_validator("readings")
    @classmethod
    def unique_variables(cls, readings):
        if len({row.variable for row in readings}) != len(readings):
            raise ValueError("No se puede repetir una variable en la misma petición.")
        return readings


class ReadingsInserted(BaseModel):
    inserted: int
    already_present: int


class SensorReadingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    device_id: UUID
    observed_at: datetime
    variable: str
    raw_value: float
    calibrated_value: float | None
    unit: str
    quality_flag: str | None
    received_at: datetime

    @field_validator("observed_at", "received_at")
    @classmethod
    def utc_timestamp(cls, value: datetime):
        # SQLite devuelve fechas sin zona; las lecturas se almacenan en UTC.
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
