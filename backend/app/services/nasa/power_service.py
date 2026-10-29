"""Cliente asíncrono reutilizable de NASA POWER."""

import logging
from typing import Any

import httpx

from app.core.config import POWER_PARAMETERS, settings
from app.core.exceptions import ExternalServiceError, ExternalServiceTimeoutError

logger = logging.getLogger(__name__)


class PowerServiceError(ExternalServiceError):
    """Error específico de POWER, compatible con la interfaz anterior."""


class PowerService:
    """Consulta las series diarias y conserva la procedencia para persistencia."""

    def __init__(
        self,
        base_url: str | None = None,
        community: str | None = None,
        parameters: tuple[str, ...] | list[str] = POWER_PARAMETERS,
        timeout: float | None = None,
    ) -> None:
        self.base_url = base_url or settings.nasa_power_base_url
        self.community = community or settings.nasa_power_community
        self.parameters = tuple(parameters)
        self.timeout = timeout if timeout is not None else settings.nasa_power_timeout

    async def get_daily_payload(
        self, latitude: float, longitude: float, start: str, end: str
    ) -> dict[str, Any]:
        """Consulta la respuesta completa de NASA POWER con metadatos de variables y versión."""
        params = {
            "parameters": ",".join(self.parameters),
            "community": self.community,
            "latitude": latitude,
            "longitude": longitude,
            "start": start,
            "end": end,
            "format": "JSON",
        }
        logger.info("Consultando NASA POWER para (lat=%s, lon=%s)", latitude, longitude)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.warning("Timeout consultando NASA POWER")
            raise ExternalServiceTimeoutError("NASA POWER agotó el tiempo de espera.") from exc
        except httpx.HTTPStatusError as exc:
            upstream_status = exc.response.status_code
            status_code = 422 if upstream_status == 422 else 503 if upstream_status == 429 else 502
            logger.warning("NASA POWER devolvió HTTP %s", upstream_status)
            detail = self._extract_upstream_error(exc.response)
            raise PowerServiceError(
                f"NASA POWER devolvió HTTP {upstream_status}: {detail}",
                status_code=status_code,
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Error comunicándose con NASA POWER: %s", exc)
            raise ExternalServiceError("No se pudo conectar con NASA POWER.") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceError("NASA POWER devolvió JSON inválido.") from exc
        if not isinstance(payload, dict):
            raise ExternalServiceError("NASA POWER devolvió una respuesta inesperada.")
        properties = payload.get("properties")
        values = properties.get("parameter") if isinstance(properties, dict) else None
        if not isinstance(values, dict) or not values:
            raise ExternalServiceError("NASA POWER no devolvió datos climáticos.")
        logger.info("Consulta NASA POWER completada exitosamente")
        return payload

    @staticmethod
    def _extract_upstream_error(response: httpx.Response) -> str:
        """Extrae el mensaje de error estructurado de NASA POWER."""
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            messages = payload.get("messages")
            if isinstance(messages, list):
                details = "; ".join(item for item in messages if isinstance(item, str))
                if details:
                    return details[:300]
            detail = payload.get("detail")
            if isinstance(detail, list):
                msgs = [
                    d.get("msg", str(d)) if isinstance(d, dict) else str(d)
                    for d in detail
                ]
                if msgs:
                    return "; ".join(msgs)[:300]
            if isinstance(detail, str):
                return detail[:300]
        return response.text[:300] or "Sin detalles adicionales."

    async def get_daily_data(
        self, latitude: float, longitude: float, start: str, end: str
    ) -> dict[str, Any]:
        """Consulta únicamente el diccionario de variables y valores por fecha."""
        payload = await self.get_daily_payload(latitude, longitude, start, end)
        return payload["properties"]["parameter"]

    # Alias convenientes para interoperabilidad
    get_daily_power_data = get_daily_data
    get_power_data = get_daily_data


power_service = PowerService()


async def get_daily_power_data(
    latitude: float, longitude: float, start_date: str, end_date: str
) -> dict[str, Any]:
    """Interfaz conservada para la ruta pública existente."""
    return await power_service.get_daily_data(latitude, longitude, start_date, end_date)
