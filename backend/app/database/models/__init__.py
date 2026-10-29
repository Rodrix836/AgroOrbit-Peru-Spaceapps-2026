"""Modelos ORM y metadatos de la base de datos."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.database.models.user import AppUser  # noqa: E402
from app.database.models.agronomic_source import AgronomicSource  # noqa: E402
from app.database.models.crop import Crop  # noqa: E402
from app.database.models.crop_requirement import CropRequirement  # noqa: E402
from app.database.models.rotation_rule import RotationRule  # noqa: E402
from app.database.models.plot import Plot  # noqa: E402
from app.database.models.nasa_observation import NasaObservation  # noqa: E402
from app.database.models.crop_cycle import CropCycle  # noqa: E402
from app.database.models.device import Device  # noqa: E402
from app.database.models.sensor_reading import SensorReading  # noqa: E402
from app.database.models.indicator import Indicator  # noqa: E402
from app.database.models.recommendation import Recommendation  # noqa: E402
from app.database.models.recommendation_item import RecommendationItem  # noqa: E402
from app.database.models.rotation_plan import RotationPlan  # noqa: E402

__all__ = [
    "Base", "AppUser", "AgronomicSource", "Crop", "CropRequirement",
    "RotationRule", "Plot", "NasaObservation", "CropCycle", "Device",
    "SensorReading", "Indicator", "Recommendation", "RecommendationItem",
    "RotationPlan",
]
