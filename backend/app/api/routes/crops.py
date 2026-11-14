"""Catálogo público de cultivos; no ofrece operaciones de escritura."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.database.models.crop import Crop
from app.database.models.crop_requirement import CropRequirement
from app.schemas.crop import CropDetail, CropRead

router = APIRouter(prefix="/crops", tags=["Cultivos"])


@router.get("", response_model=list[CropRead])
def list_crops(session: DbSession) -> list[Crop]:
    return list(session.scalars(
        select(Crop).where(Crop.is_active.is_(True)).order_by(Crop.name, Crop.id)
    ))


@router.get("/{crop_id}", response_model=CropDetail)
def get_crop(crop_id: UUID, session: DbSession) -> Crop:
    crop = session.scalar(
        select(Crop).where(Crop.id == crop_id, Crop.is_active.is_(True)).options(
            selectinload(Crop.requirements).selectinload(CropRequirement.source),
            selectinload(Crop.cycle_source),
        )
    )
    if crop is None:
        raise HTTPException(status_code=404, detail="Cultivo no encontrado.")
    return crop
