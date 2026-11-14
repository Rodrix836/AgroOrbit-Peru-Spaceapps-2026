"""Perfil privado asociado a la identidad autenticada."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import AuthId, DbSession
from app.database.models.user import AppUser
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["Usuarios"])


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
