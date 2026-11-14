"""Campañas privadas de una parcela propia."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AuthId, DbSession, owned_plot
from app.database.models.crop import Crop
from app.database.models.crop_cycle import CropCycle
from app.schemas.crop_cycle import (
    CropCycleCreate, CropCyclePatch, CropCycleRead, validate_cycle_dates,
)

router = APIRouter(prefix="/plots", tags=["Campañas"])
ACTIVE_CONFLICT = "La parcela ya tiene una campaña activa."


def active_cycle(session: Session, plot_id: UUID, exclude_id: UUID | None = None) -> bool:
    query = select(CropCycle.id).where(CropCycle.plot_id == plot_id, CropCycle.status == "active")
    if exclude_id is not None:
        query = query.where(CropCycle.id != exclude_id)
    return session.scalar(query.limit(1)) is not None


def commit_cycle(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        sqlite_conflict = (
            getattr(exc.orig, "sqlite_errorname", None) == "SQLITE_CONSTRAINT_UNIQUE"
            and "crop_cycle.plot_id" in str(exc.orig)
        )
        if constraint == "crop_cycle_one_active_per_plot_idx" or sqlite_conflict:
            raise HTTPException(status_code=409, detail=ACTIVE_CONFLICT) from exc
        raise


def read_cycle(cycle: CropCycle, crop: Crop) -> CropCycleRead:
    return CropCycleRead(
        id=cycle.id, plot_id=cycle.plot_id, crop_id=cycle.crop_id,
        crop_code=crop.code, crop_name=crop.name, sowing_date=cycle.sowing_date,
        harvest_date=cycle.harvest_date, status=cycle.status, origin=cycle.origin,
        created_at=cycle.created_at,
    )


@router.post("/{plot_id}/crop-cycles", response_model=CropCycleRead, status_code=201)
def create_cycle(plot_id: UUID, body: CropCycleCreate, auth_id: AuthId, session: DbSession):
    owned_plot(session, auth_id, plot_id)
    crop = session.scalar(select(Crop).where(Crop.id == body.crop_id, Crop.is_active.is_(True)))
    if crop is None:
        raise HTTPException(status_code=404, detail="Cultivo no encontrado.")
    if body.status == "active" and active_cycle(session, plot_id):
        raise HTTPException(status_code=409, detail=ACTIVE_CONFLICT)
    cycle = CropCycle(plot_id=plot_id, origin="farmer", **body.model_dump())
    session.add(cycle)
    commit_cycle(session)
    session.refresh(cycle)
    return read_cycle(cycle, crop)


@router.get("/{plot_id}/crop-cycles", response_model=list[CropCycleRead])
def list_cycles(plot_id: UUID, auth_id: AuthId, session: DbSession):
    owned_plot(session, auth_id, plot_id)
    rows = session.execute(
        select(CropCycle, Crop).join(Crop, Crop.id == CropCycle.crop_id)
        .where(CropCycle.plot_id == plot_id)
        .order_by(CropCycle.sowing_date.desc(), CropCycle.created_at.desc(), CropCycle.id)
    )
    return [read_cycle(cycle, crop) for cycle, crop in rows]


@router.patch("/{plot_id}/crop-cycles/{cycle_id}", response_model=CropCycleRead)
def update_cycle(
    plot_id: UUID, cycle_id: UUID, body: CropCyclePatch, auth_id: AuthId, session: DbSession,
):
    owned_plot(session, auth_id, plot_id)
    row = session.execute(
        select(CropCycle, Crop).join(Crop, Crop.id == CropCycle.crop_id)
        .where(CropCycle.id == cycle_id, CropCycle.plot_id == plot_id)
        .with_for_update(of=CropCycle)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Campaña no encontrada.")
    cycle, crop = row
    changes = body.model_dump(exclude_unset=True)
    status = changes.get("status", cycle.status)
    harvest_date = changes.get("harvest_date", cycle.harvest_date)
    try:
        validate_cycle_dates(cycle.sowing_date, harvest_date, status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if status == "active" and active_cycle(session, plot_id, exclude_id=cycle.id):
        raise HTTPException(status_code=409, detail=ACTIVE_CONFLICT)
    cycle.status = status
    cycle.harvest_date = harvest_date
    commit_cycle(session)
    session.refresh(cycle)
    return read_cycle(cycle, crop)
