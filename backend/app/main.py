"""Punto de entrada de la API de AgroOrbit Perú."""

from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(
    title="AgroOrbit Perú API",
    description="API agroclimática inicial de AgroOrbit Perú.",
    version="0.1.0",
)
app.include_router(api_router)


@app.get("/", tags=["Estado"])
async def root() -> dict[str, str]:
    return {"project": "AgroOrbit Perú", "status": "running"}


@app.get("/health", tags=["Estado"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
