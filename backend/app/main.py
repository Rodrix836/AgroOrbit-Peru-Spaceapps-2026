"""Punto de entrada de la API de AgroOrbit Perú."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import ConfigurationError
from app.core.logging import configure_logging

configure_logging(debug=settings.debug)

app = FastAPI(
    title=settings.app_name,
    description="API agroclimática inicial de AgroOrbit Perú.",
    version=settings.app_version,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.exception_handler(ConfigurationError)
async def handle_configuration_error(
    _request: Request, exc: ConfigurationError
) -> JSONResponse:
    detail = str(exc)
    if settings.app_env.strip().lower() not in {"development", "testing"}:
        detail = "El servicio no está disponible en este momento."
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.get("/", tags=["Estado"])
async def root() -> dict[str, str]:
    return {"project": "AgroOrbit Perú", "status": "running"}


@app.get("/health", tags=["Estado"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
