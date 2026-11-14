"""Resultado reproducible de una ejecución del motor de recomendaciones."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base


PRIORITIES = (
    "'save_water', 'improve_soil', 'reduce_climate_risk', "
    "'diversify', 'maintain_productivity'"
)


class Recommendation(Base):
    __tablename__ = "recommendation"
    __table_args__ = (
        CheckConstraint("horizon_days BETWEEN 1 AND 730", name="recommendation_horizon"),
        CheckConstraint(f"priority IN ({PRIORITIES})", name="recommendation_priority"),
        CheckConstraint("status IN ('ready', 'insufficient_data')", name="recommendation_status"),
        CheckConstraint(
            "confidence IN ('high', 'medium', 'low', 'insufficient')",
            name="recommendation_confidence",
        ),
        CheckConstraint(
            "(status = 'ready' AND recommended_crop_id IS NOT NULL AND confidence <> 'insufficient') "
            "OR (status = 'insufficient_data' AND recommended_crop_id IS NULL "
            "AND confidence = 'insufficient')",
            name="recommendation_status_crop",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    plot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("plot.id", ondelete="CASCADE"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)
    engine_version: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[str] = mapped_column(String, nullable=False)
    recommended_crop_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crop.id", ondelete="RESTRICT")
    )
    input_snapshot: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    summary: Mapped[str | None] = mapped_column(String)
