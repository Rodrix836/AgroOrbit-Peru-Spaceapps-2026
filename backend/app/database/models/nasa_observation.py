"""Valor NASA normalizado para una parcela y un instante."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models import Base


class NasaObservation(Base):
    __tablename__ = "nasa_observation"
    __table_args__ = (
        UniqueConstraint(
            "plot_id", "dataset", "dataset_version", "variable", "observed_at",
            name="nasa_observation_unique_value",
        ),
        Index("nasa_observation_plot_time_idx", "plot_id", "observed_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    plot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("plot.id", ondelete="CASCADE"), nullable=False
    )
    dataset: Mapped[str] = mapped_column(String(80), nullable=False)
    dataset_version: Mapped[str] = mapped_column(
        String(40), nullable=False, default="unspecified", server_default="unspecified"
    )
    collection_concept_id: Mapped[str | None] = mapped_column(String)
    grid_cell_key: Mapped[str | None] = mapped_column(String)
    variable: Mapped[str] = mapped_column(String(80), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    quality_flag: Mapped[str | None] = mapped_column(String(40))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    plot: Mapped["Plot"] = relationship(back_populates="observations")
