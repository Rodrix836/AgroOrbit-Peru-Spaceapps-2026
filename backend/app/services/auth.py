"""Identidad verificada por Supabase Auth para las rutas con datos privados."""

from pathlib import Path
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


auth_settings = AuthSettings()
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_auth_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UUID:
    """Consulta al servidor Auth: nunca acepta un user_id declarado por el cliente."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Se requiere un token de usuario.")
    if not auth_settings.supabase_url or not auth_settings.supabase_publishable_key:
        raise HTTPException(status_code=503, detail="Supabase Auth no está configurado.")

    url = auth_settings.supabase_url.rstrip("/") + "/auth/v1/user"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                url,
                headers={
                    "apikey": auth_settings.supabase_publishable_key,
                    "Authorization": f"Bearer {credentials.credentials}",
                },
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Supabase Auth no está disponible.") from exc
    if response.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="Token de usuario inválido.")
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="Supabase Auth no pudo validar el token.")
    try:
        return UUID(response.json()["id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Respuesta de identidad inválida.") from exc
