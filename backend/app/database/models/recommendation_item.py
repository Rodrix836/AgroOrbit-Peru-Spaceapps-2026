"""Candidato evaluado y explicación de su posición o descarte."""

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base


class RecommendationItem(Base):
    __tablename__ = "recommendation_item"
    __table_args__ = (
        CheckConstraint("rank > 0", name="recommendation_item_rank_positive"),
        CheckConstraint("score BETWEEN 0 AND 1", name="recommendation_item_score"),
        CheckConstraint(
            "(eligible AND rank IS NOT NULL AND score IS NOT NULL AND exclusion_reason IS NULL) "
            "OR (NOT eligible AND rank IS NULL AND score IS NULL "
            "AND exclusion_reason IS NOT NULL)",
            name="recommendation_item_eligibility",
        ),
        UniqueConstraint("recommendation_id", "crop_id", name="recommendation_item_unique_crop"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    recommendation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("recommendation.id", ondelete="CASCADE"),
        nullable=False,
    )
    crop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crop.id", ondelete="RESTRICT"), nullable=False
    )
    rank: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reasons: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list
    )
    limiting_factors: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list
    )
    exclusion_reason: Mapped[str | None] = mapped_column(String)
