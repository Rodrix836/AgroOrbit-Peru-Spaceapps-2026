"""Parcelas consultables únicamente por su propietario."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.plot import Plot
from app.database.models.user import AppUser
from app.database.session import get_db_session
from app.services.auth import get_current_auth_user_id

router = APIRouter(prefix="/plots", tags=["Parcelas"])
AuthId = Annotated[UUID, Depends(get_current_auth_user_id)]
DbSession = Annotated[Session, Depends(get_db_session)]


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


def owned_plot(session: Session, auth_id: UUID, plot_id: UUID) -> Plot:
    plot = session.scalar(
        select(Plot).join(AppUser).where(
            Plot.id == plot_id, AppUser.auth_user_id == auth_id
        )
    )
    if plot is None:
        raise HTTPException(status_code=404, detail="Parcela no encontrada.")
    return plot


@router.post("", response_model=PlotRead, status_code=201)
def create_plot(body: PlotCreate, auth_id: AuthId, session: DbSession) -> Plot:
    profile = session.scalar(select(AppUser).where(AppUser.auth_user_id == auth_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Primero crea tu perfil.")
    fields = body.model_dump()
    fields["name"] = body.name.strip()
    if not fields["name"]:
        raise HTTPException(status_code=422, detail="El nombre no puede estar vacío.")
    plot = Plot(user_id=profile.id, **fields)
    session.add(plot)
    session.commit()
    session.refresh(plot)
    return plot


@router.get("", response_model=list[PlotRead])
def list_my_plots(auth_id: AuthId, session: DbSession) -> list[Plot]:
    return list(session.scalars(
        select(Plot).join(AppUser).where(AppUser.auth_user_id == auth_id)
        .order_by(Plot.created_at.desc())
    ))


@router.get("/{plot_id}", response_model=PlotRead)
def get_plot(plot_id: UUID, auth_id: AuthId, session: DbSession) -> Plot:
    return owned_plot(session, auth_id, plot_id)
