"""Paso de una rotación propuesta, con fechas reales y base climática."""

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base


class RotationPlan(Base):
    __tablename__ = "rotation_plan"
    __table_args__ = (
        CheckConstraint("step > 0", name="rotation_plan_step_positive"),
        CheckConstraint("action IN ('crop', 'fallow')", name="rotation_plan_action"),
        CheckConstraint("climate_basis IN ('recent', 'historical')", name="rotation_plan_climate_basis"),
        CheckConstraint("confidence IN ('high', 'medium', 'low')", name="rotation_plan_confidence"),
        CheckConstraint("end_on >= start_on", name="rotation_plan_dates"),
        CheckConstraint(
            "(action = 'crop' AND crop_id IS NOT NULL) OR "
            "(action = 'fallow' AND crop_id IS NULL)",
            name="rotation_plan_action_crop",
        ),
        UniqueConstraint("recommendation_id", "step", name="rotation_plan_unique_step"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    recommendation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("recommendation.id", ondelete="CASCADE"),
        nullable=False,
    )
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    crop_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crop.id", ondelete="RESTRICT")
    )
    start_on: Mapped[date] = mapped_column(Date, nullable=False)
    end_on: Mapped[date] = mapped_column(Date, nullable=False)
    climate_basis: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(String)
