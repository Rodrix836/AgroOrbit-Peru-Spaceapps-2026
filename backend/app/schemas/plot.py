"""Esquemas de parcelas declaradas por el agricultor."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    area_ha: float | None = Field(default=None, gt=0)
    water_source: str | None = None
    water_availability: Literal["low", "medium", "high"] | None = None
    soil_texture: str | None = None
    soil_ph: float | None = Field(default=None, ge=0, le=14)
    soil_salinity_ds_m: float | None = Field(default=None, ge=0)
    priority: Literal[
        "save_water", "improve_soil", "reduce_climate_risk",
        "diversify", "maintain_productivity",
    ] | None = None
    declared_irrigated: bool | None = None


class PlotRead(PlotCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    created_at: datetime
