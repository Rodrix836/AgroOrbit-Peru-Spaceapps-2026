"""Parcelas consultables únicamente por su propietario."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import AuthId, DbSession, owned_plot
from app.database.models.plot import Plot
from app.database.models.user import AppUser
from app.schemas.plot import PlotCreate, PlotRead

router = APIRouter(prefix="/plots", tags=["Parcelas"])


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
