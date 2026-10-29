"""Registro central de rutas de la API."""

from fastapi import APIRouter

from app.api.routes import nasa

api_router = APIRouter(prefix="/api")
api_router.include_router(nasa.router)
