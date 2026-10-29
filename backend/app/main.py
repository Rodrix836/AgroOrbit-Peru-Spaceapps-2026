"""Punto de entrada de la API de AgroOrbit Perú."""

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="API agroclimática inicial de AgroOrbit Perú.",
    version=settings.app_version,
)
app.include_router(api_router)


@app.get("/", tags=["Estado"])
async def root() -> dict[str, str]:
    return {"project": "AgroOrbit Perú", "status": "running"}


@app.get("/health", tags=["Estado"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
