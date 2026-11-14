"""Historial de siembra de una parcela, basado en fechas reales."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base


class CropCycle(Base):
    __tablename__ = "crop_cycle"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'finished', 'planned')", name="crop_cycle_status"),
        CheckConstraint("origin IN ('farmer', 'recommendation')", name="crop_cycle_origin"),
        CheckConstraint("harvest_date IS NULL OR harvest_date >= sowing_date", name="crop_cycle_dates"),
        CheckConstraint("status <> 'finished' OR harvest_date IS NOT NULL", name="crop_cycle_finished_date"),
        Index(
            "crop_cycle_one_active_per_plot_idx", "plot_id", unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    plot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("plot.id", ondelete="CASCADE"), nullable=False
    )
    crop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crop.id", ondelete="RESTRICT"), nullable=False
    )
    sowing_date: Mapped[date] = mapped_column(Date, nullable=False)
    harvest_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String, nullable=False)
    origin: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
