"""Perfil privado asociado a la identidad autenticada."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.user import AppUser
from app.database.session import get_db_session
from app.services.auth import get_current_auth_user_id

router = APIRouter(prefix="/users", tags=["Usuarios"])
AuthId = Annotated[UUID, Depends(get_current_auth_user_id)]
DbSession = Annotated[Session, Depends(get_db_session)]


class UserCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    display_name: str
    created_at: datetime


@router.post("/me", response_model=UserRead)
def create_my_profile(body: UserCreate, auth_id: AuthId, session: DbSession) -> AppUser:
    existing = session.scalar(select(AppUser).where(AppUser.auth_user_id == auth_id))
    if existing:
        return existing
    name = body.display_name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="El nombre no puede estar vacío.")
    profile = AppUser(auth_user_id=auth_id, display_name=name)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.get("/me", response_model=UserRead)
def get_my_profile(auth_id: AuthId, session: DbSession) -> AppUser:
    profile = session.scalar(select(AppUser).where(AppUser.auth_user_id == auth_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Primero crea tu perfil.")
    return profile
