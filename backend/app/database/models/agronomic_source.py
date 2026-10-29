"""Referencia verificable de un valor o una regla agronómica."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base


class AgronomicSource(Base):
    __tablename__ = "agronomic_source"
    __table_args__ = (
        CheckConstraint("length(trim(citation)) > 0", name="agronomic_source_citation"),
        CheckConstraint(
            "publication_year BETWEEN 1800 AND 2100", name="agronomic_source_year"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    citation: Mapped[str] = mapped_column(String, nullable=False)
    publisher: Mapped[str | None] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(String)
    publication_year: Mapped[int | None] = mapped_column(Integer)
    accessed_at: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
