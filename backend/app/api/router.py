"""Registro central de rutas de la API."""

from fastapi import APIRouter

from app.api.routes import nasa, plot_nasa, plots, users

api_router = APIRouter(prefix="/api")
api_router.include_router(nasa.router)
api_router.include_router(users.router)
api_router.include_router(plots.router)
api_router.include_router(plot_nasa.router)
