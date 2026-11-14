"""Regla agronómica documentada para transiciones de cultivos."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base


class RotationRule(Base):
    __tablename__ = "rotation_rule"
    __table_args__ = (
        CheckConstraint(
            "rule_kind IN ('same_crop', 'same_family', 'crop_pair', 'family_pair', 'group_pair')",
            name="rotation_rule_kind",
        ),
        CheckConstraint("effect IN ('benefit', 'penalty', 'exclude')", name="rotation_rule_effect"),
        CheckConstraint("weight BETWEEN 0 AND 1", name="rotation_rule_weight"),
        CheckConstraint("evidence_level IN ('A', 'B', 'C')", name="rotation_rule_evidence"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    rule_kind: Mapped[str] = mapped_column(String, nullable=False)
    predecessor_crop_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crop.id", ondelete="RESTRICT")
    )
    successor_crop_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crop.id", ondelete="RESTRICT")
    )
    predecessor_family: Mapped[str | None] = mapped_column(String)
    successor_family: Mapped[str | None] = mapped_column(String)
    predecessor_group: Mapped[str | None] = mapped_column(String)
    successor_group: Mapped[str | None] = mapped_column(String)
    effect: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    rationale: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agronomic_source.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evidence_level: Mapped[str] = mapped_column(String, nullable=False)
    region_validity: Mapped[str | None] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
