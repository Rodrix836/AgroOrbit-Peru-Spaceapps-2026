"""Entrada y lectura de campañas declaradas por el agricultor."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

CycleStatus = Literal["active", "finished", "planned"]


def validate_cycle_dates(sowing_date: date, harvest_date: date | None, status: str) -> None:
    if harvest_date is not None and harvest_date < sowing_date:
        raise ValueError("harvest_date no puede ser anterior a sowing_date.")
    if status == "finished" and harvest_date is None:
        raise ValueError("Una campaña finalizada requiere harvest_date.")


class CropCycleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    crop_id: UUID
    sowing_date: date
    harvest_date: date | None = None
    status: CycleStatus

    @model_validator(mode="after")
    def valid_dates(self):
        validate_cycle_dates(self.sowing_date, self.harvest_date, self.status)
        return self


class CropCyclePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: CycleStatus | None = None
    harvest_date: date | None = None

    @model_validator(mode="after")
    def valid_changes(self):
        if not self.model_fields_set:
            raise ValueError("Envía status y/o harvest_date.")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status no puede ser null.")
        return self


class CropCycleRead(BaseModel):
    id: UUID
    plot_id: UUID
    crop_id: UUID
    crop_code: str
    crop_name: str
    sowing_date: date
    harvest_date: date | None
    status: CycleStatus
    origin: Literal["farmer", "recommendation"]
    created_at: datetime
