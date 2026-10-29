"""Cliente asíncrono para la API diaria de NASA POWER."""

import logging
from typing import Any

import httpx

from app.core.config import POWER_PARAMETERS, settings
from app.core.exceptions import ExternalServiceError, ExternalServiceTimeoutError

logger = logging.getLogger(__name__)


async def get_daily_power_data(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Obtiene las series diarias solicitadas para un punto y un período."""

    params = {
        "parameters": ",".join(POWER_PARAMETERS),
        "community": settings.nasa_power_community,
        "latitude": latitude,
        "longitude": longitude,
        "start": start_date,
        "end": end_date,
        "format": "JSON",
    }

    logger.info("Consultando NASA POWER")
    try:
        async with httpx.AsyncClient(timeout=settings.nasa_power_timeout) as client:
            response = await client.get(settings.nasa_power_base_url, params=params)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        logger.warning("Timeout consultando NASA POWER")
        raise ExternalServiceTimeoutError("NASA POWER agotó el tiempo de espera.") from exc
    except httpx.HTTPStatusError as exc:
        upstream_status = exc.response.status_code
        logger.warning("NASA POWER devolvió HTTP %s", upstream_status)
        if upstream_status == 422:
            status_code = 422
        elif upstream_status == 429:
            status_code = 503
        else:
            status_code = 502

        message = f"NASA POWER devolvió HTTP {upstream_status}."
        try:
            upstream_messages = exc.response.json().get("messages")
        except (ValueError, AttributeError):
            upstream_messages = None
        if isinstance(upstream_messages, list):
            details = "; ".join(item for item in upstream_messages if isinstance(item, str))
            if details:
                message = f"{message} {details[:300]}"
        raise ExternalServiceError(
            message, status_code=status_code
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Error comunicándose con NASA POWER")
        raise ExternalServiceError("No se pudo conectar con NASA POWER.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        logger.error("NASA POWER devolvió JSON inválido")
        raise ExternalServiceError("NASA POWER devolvió una respuesta JSON inválida.") from exc

    if not isinstance(payload, dict):
        logger.error("NASA POWER devolvió una respuesta inesperada")
        raise ExternalServiceError("NASA POWER devolvió una respuesta inesperada.")

    properties = payload.get("properties")
    parameters = properties.get("parameter") if isinstance(properties, dict) else None
    if not isinstance(parameters, dict) or not parameters:
        logger.error("NASA POWER no devolvió datos climáticos")
        raise ExternalServiceError("NASA POWER no devolvió datos climáticos para la consulta.")

    logger.info("Consulta NASA POWER completada")
    return parameters
