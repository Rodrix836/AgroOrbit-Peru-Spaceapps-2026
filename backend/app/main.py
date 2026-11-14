"""Punto de entrada de la API de AgroOrbit Perú."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AgroOrbitError, ExternalServiceError
from app.core.logging import configure_logging

configure_logging(debug=settings.debug)
logger = logging.getLogger(__name__)

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


@app.exception_handler(AgroOrbitError)
@app.exception_handler(ExternalServiceError)
async def handle_agroorbit_error(request: Request, exc: AgroOrbitError) -> JSONResponse:
    logger.error(
        "%s %s: %s", request.method, request.url.path, exc, exc_info=True
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.get("/", tags=["Estado"])
async def root() -> dict[str, str]:
    return {"project": "AgroOrbit Perú", "status": "running"}


@app.get("/health", tags=["Estado"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
