"""Configuración y creación diferida de la conexión PostgreSQL."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url


class DatabaseSettings(BaseSettings):
    """Lee la cadena de conexión sin exigirla al iniciar la API."""

    database_url: str | None = Field(default=None, repr=False)

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def normalize_database_url(database_url: str) -> URL:
    """Acepta la URL PostgreSQL que entrega Supabase con el driver psycopg 3."""

    url = make_url(database_url)
    if url.drivername == "postgresql":
        return url.set(drivername="postgresql+psycopg")
    return url


def make_engine(database_url: str) -> Engine:
    """Crea un motor reutilizable; no abre la conexión hasta la primera consulta."""

    return create_engine(normalize_database_url(database_url), pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Comparte el pool entre solicitudes de FastAPI."""

    database_url = DatabaseSettings().database_url
    if not database_url:
        raise RuntimeError("Falta DATABASE_URL para conectar con Supabase PostgreSQL")
    return make_engine(database_url)
