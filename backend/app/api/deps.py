"""Dependencias compartidas para identidad, sesiones y acceso a parcelas."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.plot import Plot
from app.database.models.user import AppUser
from app.database.session import get_db_session
from app.services.auth import get_current_auth_user_id

AuthId = Annotated[UUID, Depends(get_current_auth_user_id)]
DbSession = Annotated[Session, Depends(get_db_session)]


def owned_plot(session: Session, auth_id: UUID, plot_id: UUID) -> Plot:
    """Devuelve una parcela propia; oculta las ajenas y las inexistentes."""
    plot = session.scalar(
        select(Plot).join(AppUser).where(
            Plot.id == plot_id, AppUser.auth_user_id == auth_id
        )
    )
    if plot is None:
        raise HTTPException(status_code=404, detail="Parcela no encontrada.")
    return plot
