"""Perfil de AgroOrbit; auth_user_id enlaza opcionalmente con Supabase Auth."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models import Base


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (CheckConstraint("length(trim(display_name)) > 0", name="app_user_name"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    # La migración PostgreSQL añade la FK a auth.users. Se omite aquí para que
    # la prueba de modelos pueda ejecutarse también con SQLite.
    auth_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    plots: Mapped[list["Plot"]] = relationship(back_populates="user")
