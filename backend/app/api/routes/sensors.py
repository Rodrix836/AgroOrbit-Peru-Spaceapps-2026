"""Registro privado de kits e ingesta autenticada con la clave del dispositivo."""

from datetime import datetime, timezone
import hashlib
import hmac
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from app.api.deps import AuthId, DbSession, owned_plot
from app.database.models.device import Device
from app.database.models.sensor_reading import SensorReading
from app.schemas.sensor import (
    DeviceCreate, DeviceRead, DeviceRegistered, ReadingsCreate, ReadingsInserted,
    SensorReadingRead, SensorVariable,
)

router = APIRouter(tags=["Sensores"])


@router.post("/plots/{plot_id}/devices", response_model=DeviceRegistered, status_code=201)
def register_device(plot_id: UUID, body: DeviceCreate, auth_id: AuthId, session: DbSession):
    owned_plot(session, auth_id, plot_id)
    if session.scalar(select(Device.id).where(Device.external_id == body.external_id)) is not None:
        raise HTTPException(status_code=409, detail="El external_id ya está registrado.")
    secret = secrets.token_urlsafe(32)
    device = Device(plot_id=plot_id, secret_hash=hashlib.sha256(secret.encode()).hexdigest(),
                    **body.model_dump())
    session.add(device)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        sqlite_conflict = (
            getattr(exc.orig, "sqlite_errorname", None) == "SQLITE_CONSTRAINT_UNIQUE"
            and "device.external_id" in str(exc.orig)
        )
        if constraint == "device_external_id_key" or sqlite_conflict:
            raise HTTPException(status_code=409, detail="El external_id ya está registrado.") from exc
        raise
    session.refresh(device)
    return DeviceRegistered(**DeviceRead.model_validate(device).model_dump(), secret=secret)


@router.get("/plots/{plot_id}/devices", response_model=list[DeviceRead])
def list_devices(plot_id: UUID, auth_id: AuthId, session: DbSession):
    owned_plot(session, auth_id, plot_id)
    return list(session.scalars(
        select(Device).where(Device.plot_id == plot_id).order_by(Device.created_at.desc(), Device.id)
    ))


@router.post("/devices/readings", response_model=ReadingsInserted, status_code=201)
def receive_readings(
    body: ReadingsCreate, session: DbSession,
    device_key: Annotated[str | None, Header(alias="X-Device-Key")] = None,
):
    device = session.scalar(select(Device).where(Device.external_id == body.external_id))
    supplied_hash = hashlib.sha256((device_key or "").encode()).hexdigest()
    stored_hash = device.secret_hash if device and device.secret_hash else "0" * 64
    valid_key = hmac.compare_digest(supplied_hash, stored_hash)
    if (not device_key or not valid_key or device is None
            or not device.secret_hash or device.status != "active"):
        raise HTTPException(status_code=401, detail="Credenciales del dispositivo inválidas.")
    observed_at = body.observed_at or datetime.now(timezone.utc).replace(microsecond=0)
    values = [dict(device_id=device.id, observed_at=observed_at, **row.model_dump())
              for row in body.readings]
    dialect = session.get_bind().dialect.name
    insert = sqlite_insert if dialect == "sqlite" else postgres_insert
    statement = insert(SensorReading).values(values).on_conflict_do_nothing(
        index_elements=["device_id", "variable", "observed_at"],
    ).returning(SensorReading.id)
    inserted = len(session.scalars(statement).all())
    session.commit()
    return ReadingsInserted(inserted=inserted, already_present=len(values) - inserted)


@router.get("/plots/{plot_id}/sensors/readings", response_model=list[SensorReadingRead])
def list_readings(
    plot_id: UUID, auth_id: AuthId, session: DbSession,
    variable: SensorVariable | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
):
    owned_plot(session, auth_id, plot_id)
    query = (
        select(SensorReading).join(Device, Device.id == SensorReading.device_id)
        .where(Device.plot_id == plot_id)
    )
    if variable is not None:
        query = query.where(SensorReading.variable == variable)
    return list(session.scalars(query.order_by(
        SensorReading.observed_at.desc(), SensorReading.variable, SensorReading.id,
    ).limit(limit)))
