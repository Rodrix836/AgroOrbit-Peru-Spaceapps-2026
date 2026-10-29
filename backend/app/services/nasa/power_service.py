"""Cliente asíncrono y servicio para la API diaria de NASA POWER."""

import logging
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import (
    POWER_BASE_URL,
    POWER_COMMUNITY,
    POWER_PARAMETERS,
    POWER_TIMEOUT_SECONDS,
)


class PowerService:
    """Servicio para consultar la API de NASA POWER de forma asíncrona."""

    def __init__(
        self,
        base_url: str = POWER_BASE_URL,
        community: str = POWER_COMMUNITY,
        parameters: tuple[str, ...] | list[str] = POWER_PARAMETERS,
        timeout: float = POWER_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url
        self.community = community
        self.parameters = tuple(parameters)
        self.timeout = timeout

    async def get_daily_data(
        self,
        latitude: float,
        longitude: float,
        start: str,
        end: str,
    ) -> dict[str, Any]:
        """Consulta datos agroclimáticos diarios de NASA POWER para un punto y período.

        Args:
            latitude: Latitud geográfica en grados decimales (float entre -90 y 90).
            longitude: Longitud geográfica en grados decimales (float entre -180 y 180).
            start: Fecha de inicio en formato AAAAMMDD (str).
            end: Fecha de fin en formato AAAAMMDD (str).

        Returns:
            dict[str, Any]: Diccionario con las series temporales por parámetro climático.

        Raises:
            HTTPException: Si ocurre un error de conexión, timeout o respuesta fallida de NASA POWER.
        """
        params = {
            "parameters": ",".join(self.parameters),
            "community": self.community,
            "latitude": latitude,
            "longitude": longitude,
            "start": start,
            "end": end,
            "format": "JSON",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()

        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="NASA POWER agotó el tiempo de espera al procesar la solicitud.",
            ) from exc

        except httpx.HTTPStatusError as exc:
            upstream_status = exc.response.status_code
            detail_msg = self._extract_upstream_error(exc.response)

            if upstream_status == 422:
                client_status = status.HTTP_422_UNPROCESSABLE_ENTITY
            elif upstream_status == 429:
                client_status = status.HTTP_503_SERVICE_UNAVAILABLE
            else:
                client_status = status.HTTP_502_BAD_GATEWAY

            raise HTTPException(
                status_code=client_status,
                detail=f"NASA POWER devolvió un error (HTTP {upstream_status}): {detail_msg}",
            ) from exc

        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"No se pudo conectar con el servicio de NASA POWER: {str(exc)}",
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="NASA POWER devolvió una respuesta JSON inválida.",
            ) from exc

        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="NASA POWER devolvió una estructura de respuesta inesperada.",
            )

        properties = payload.get("properties")
        parameters_data = properties.get("parameter") if isinstance(properties, dict) else None
        if not isinstance(parameters_data, dict) or not parameters_data:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="NASA POWER no devolvió datos agroclimáticos para la consulta solicitada.",
            )

        return parameters_data

    def _extract_upstream_error(self, response: httpx.Response) -> str:
        """Extrae de manera limpia los mensajes de error devueltos por la API de NASA POWER."""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                # Manejar formato de lista 'messages' de NASA POWER
                messages = payload.get("messages")
                if isinstance(messages, list) and messages:
                    return "; ".join(str(m) for m in messages if m)

                # Manejar formato 'detail' estilo FastAPI / Pydantic
                detail = payload.get("detail")
                if isinstance(detail, list):
                    return "; ".join(
                        d.get("msg", str(d)) if isinstance(d, dict) else str(d) for d in detail
                    )
                if detail:
                    return str(detail)
        except Exception:
            pass

        return response.text[:250] if response.text else "Sin detalles adicionales."

    # Alias de métodos para mayor conveniencia
    get_daily_power_data = get_daily_data
    get_power_data = get_daily_data


# Instancia singleton predeterminada
power_service = PowerService()


class PowerServiceError(HTTPException):
    """Excepción mantenida para compatibilidad con versiones previas."""

    def __init__(self, message: str, status_code: int = status.HTTP_502_BAD_GATEWAY) -> None:
        super().__init__(status_code=status_code, detail=message)


async def get_daily_power_data(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Obtiene las series diarias solicitadas para un punto y un período."""

    params = {
        "parameters": ",".join(POWER_PARAMETERS),
        "community": POWER_COMMUNITY,
        "latitude": latitude,
        "longitude": longitude,
        "start": start_date,
        "end": end_date,
        "format": "JSON",
    }

    try:
        async with httpx.AsyncClient(timeout=POWER_TIMEOUT_SECONDS) as client:
            response = await client.get(POWER_BASE_URL, params=params)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise PowerServiceError(
            "NASA POWER agotó el tiempo de espera.", status_code=504
        ) from exc
    except httpx.HTTPStatusError as exc:
        upstream_status = exc.response.status_code
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
        raise PowerServiceError(
            message, status_code=status_code
        ) from exc
    except httpx.RequestError as exc:
        raise PowerServiceError("No se pudo conectar con NASA POWER.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise PowerServiceError("NASA POWER devolvió una respuesta JSON inválida.") from exc

    if not isinstance(payload, dict):
        raise PowerServiceError("NASA POWER devolvió una respuesta inesperada.")

    properties = payload.get("properties")
    parameters = properties.get("parameter") if isinstance(properties, dict) else None
    if not isinstance(parameters, dict) or not parameters:
        raise PowerServiceError("NASA POWER no devolvió datos climáticos para la consulta.")

    return parameters
