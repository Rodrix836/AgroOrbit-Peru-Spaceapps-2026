"""Rutas HTTP para datos climáticos de NASA."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from app.core.exceptions import ExternalServiceError
from app.services.nasa.power_service import get_daily_power_data

router = APIRouter(prefix="/nasa", tags=["NASA"])


def _parse_power_date(value: str, field_name: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} debe ser una fecha válida en formato AAAAMMDD.",
        ) from exc


@router.get("/power")
async def get_power(
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    start_date: Annotated[str, Query(pattern=r"^\d{8}$")],
    end_date: Annotated[str, Query(pattern=r"^\d{8}$")],
) -> dict[str, Any]:
    """Consulta las series agroclimáticas diarias de NASA POWER."""

    start = _parse_power_date(start_date, "start_date")
    end = _parse_power_date(end_date, "end_date")
    if start > end:
        raise HTTPException(
            status_code=422,
            detail="start_date no puede ser posterior a end_date.",
        )

    try:
        data = await get_daily_power_data(latitude, longitude, start_date, end_date)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return {
        "source": "NASA POWER",
        "location": {"latitude": latitude, "longitude": longitude},
        "period": {"start": start_date, "end": end_date},
        "data": data,
    }
