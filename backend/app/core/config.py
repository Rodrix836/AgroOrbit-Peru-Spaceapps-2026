"""Configuración compartida del backend y de NASA POWER."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Valores predeterminados que pueden reemplazarse con variables de entorno."""

    app_name: str = "AgroOrbit Perú API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = True

    nasa_power_base_url: str = "https://power.larc.nasa.gov/api/temporal/daily/point"
    nasa_power_community: str = "AG"
    nasa_power_timeout: float = Field(default=30, gt=0, allow_inf_nan=False)

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


POWER_PARAMETERS = (
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "PRECTOTCORR",
    "RH2M",
    "WS10M",
    "ALLSKY_SFC_SW_DWN",
)

settings = Settings()
