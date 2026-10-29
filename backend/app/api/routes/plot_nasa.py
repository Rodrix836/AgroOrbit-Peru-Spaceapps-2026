"""Consulta POWER para una parcela y lectura de observaciones persistidas."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.nasa import _parse_power_date
from app.api.routes.plots import owned_plot
from app.core.exceptions import ExternalServiceError
from app.database.models.nasa_observation import NasaObservation
from app.database.session import get_db_session
from app.services.auth import get_current_auth_user_id
from app.services.nasa.observation_service import normalize_power_payload, save_observations
from app.services.nasa.power_service import power_service

router = APIRouter(prefix="/plots", tags=["NASA por parcela"])
AuthId = Annotated[UUID, Depends(get_current_auth_user_id)]
DbSession = Annotated[Session, Depends(get_db_session)]


class ObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    dataset: str
    dataset_version: str
    variable: str
    observed_at: datetime
    value: float
    unit: str


@router.post("/{plot_id}/nasa/power")
async def fetch_and_save_power(
    plot_id: UUID,
    start_date: Annotated[str, Query(pattern=r"^\d{8}$")],
    end_date: Annotated[str, Query(pattern=r"^\d{8}$")],
    auth_id: AuthId,
    session: DbSession,
) -> dict:
    plot = owned_plot(session, auth_id, plot_id)
    if _parse_power_date(start_date, "start_date") > _parse_power_date(end_date, "end_date"):
        raise HTTPException(status_code=422, detail="start_date no puede superar end_date.")
    try:
        payload = await power_service.get_daily_payload(
            float(plot.latitude), float(plot.longitude), start_date, end_date
        )
        rows, missing = normalize_power_payload(payload, plot.id)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    inserted = save_observations(session, rows)
    return {
        "plot_id": plot.id,
        "dataset": "NASA_POWER_DAILY",
        "period": {"start": start_date, "end": end_date},
        "inserted": inserted,
        "already_present": len(rows) - inserted,
        "missing_skipped": missing,
    }


@router.get("/{plot_id}/nasa/observations", response_model=list[ObservationRead])
def list_observations(
    plot_id: UUID,
    auth_id: AuthId,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[NasaObservation]:
    owned_plot(session, auth_id, plot_id)
    return list(session.scalars(
        select(NasaObservation).where(NasaObservation.plot_id == plot_id)
        .order_by(NasaObservation.observed_at.desc(), NasaObservation.variable)
        .limit(limit)
    ))
