"""Contratos públicos de consulta del catálogo agronómico."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    citation: str
    publisher: str | None
    url: str | None
    publication_year: int | None


class CropRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    scientific_name: str | None
    botanical_family: str | None
    functional_group: str | None
    is_perennial: bool
    cycle_min_days: int | None
    cycle_max_days: int | None


class CropRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    criterion: str
    value: dict[str, Any]
    unit: str | None
    evidence_level: str
    region_validity: str | None
    notes: str | None
    source: SourceRead


class CropDetail(CropRead):
    requirements: list[CropRequirementRead]
    cycle_source: SourceRead | None
