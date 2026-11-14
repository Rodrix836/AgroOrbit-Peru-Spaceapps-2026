"""Esquemas del perfil privado del usuario."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    display_name: str
    created_at: datetime
