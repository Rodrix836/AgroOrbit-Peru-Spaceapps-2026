"""Esquemas de lectura de observaciones NASA persistidas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    dataset: str
    dataset_version: str
    variable: str
    observed_at: datetime
    value: float
    unit: str
