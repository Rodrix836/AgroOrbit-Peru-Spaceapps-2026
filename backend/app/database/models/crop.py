"""Cultivo candidato a recomendación o parte del historial."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base


class Crop(Base):
    __tablename__ = "crop"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="crop_name"),
        CheckConstraint(
            "(cycle_min_days IS NULL AND cycle_max_days IS NULL AND cycle_source_id IS NULL) "
            "OR (cycle_min_days > 0 AND cycle_max_days >= cycle_min_days "
            "AND cycle_source_id IS NOT NULL)",
            name="crop_cycle_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    scientific_name: Mapped[str | None] = mapped_column(String)
    botanical_family: Mapped[str | None] = mapped_column(String)
    functional_group: Mapped[str | None] = mapped_column(String)
    is_perennial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cycle_min_days: Mapped[int | None] = mapped_column(Integer)
    cycle_max_days: Mapped[int | None] = mapped_column(Integer)
    cycle_source_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agronomic_source.id", ondelete="RESTRICT")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
