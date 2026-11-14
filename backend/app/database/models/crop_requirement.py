"""Requisito trazable de un cultivo, por ejemplo temperatura o pH."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base


class CropRequirement(Base):
    __tablename__ = "crop_requirement"
    __table_args__ = (
        CheckConstraint("length(trim(criterion)) > 0", name="crop_requirement_criterion"),
        CheckConstraint("evidence_level IN ('A', 'B', 'C')", name="crop_requirement_evidence"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    crop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crop.id", ondelete="CASCADE"), nullable=False
    )
    criterion: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    unit: Mapped[str | None] = mapped_column(String)
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agronomic_source.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evidence_level: Mapped[str] = mapped_column(String, nullable=False)
    region_validity: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
