"""Modelos ORM y metadatos de la base de datos."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.database.models.nasa_observation import NasaObservation  # noqa: E402
from app.database.models.plot import Plot  # noqa: E402

__all__ = ["Base", "Plot", "NasaObservation"]
