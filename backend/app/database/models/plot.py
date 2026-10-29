"""Parcela registrada por el agricultor."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models import Base


class Plot(Base):
    __tablename__ = "plot"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="plot_latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="plot_longitude_range"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    observations: Mapped[list["NasaObservation"]] = relationship(back_populates="plot")
