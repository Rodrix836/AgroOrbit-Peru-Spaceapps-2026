"""Normalización e inserción idempotente de observaciones POWER."""

from datetime import datetime, timezone
import math
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.exceptions import ExternalServiceError
from app.database.models.nasa_observation import NasaObservation


def normalize_power_payload(payload: dict[str, Any], plot_id: UUID) -> tuple[list[dict], int]:
    header = payload.get("header", {})
    metadata = payload.get("parameters", {})
    properties = payload.get("properties", {})
    series = properties.get("parameter") if isinstance(properties, dict) else None
    if not isinstance(header, dict) or not isinstance(metadata, dict) or not isinstance(series, dict):
        raise ExternalServiceError("Faltan metadatos o series de NASA POWER.")
    api = header.get("api", {})
    api_version = api.get("version") if isinstance(api, dict) else None
    dataset_version = f"api-{api_version}" if api_version else "unspecified"
    fill_value = header.get("fill_value")
    try:
        fill_val_float = float(fill_value) if fill_value is not None else None
    except (ValueError, TypeError):
        fill_val_float = None

    rows: list[dict] = []
    missing = 0

    for variable, dates in series.items():
        unit_info = metadata.get(variable, {})
        unit = unit_info.get("units") if isinstance(unit_info, dict) else None
        if not isinstance(unit, str) or not unit:
            raise ExternalServiceError(f"NASA POWER no indicó la unidad de {variable}.")
        if not isinstance(dates, dict):
            raise ExternalServiceError(f"NASA POWER devolvió una serie inválida: {variable}.")
        for day, raw_value in dates.items():
            is_fill = (
                (fill_value is not None and raw_value == fill_value)
                or (
                    fill_val_float is not None
                    and isinstance(raw_value, (int, float))
                    and not isinstance(raw_value, bool)
                    and math.isclose(float(raw_value), fill_val_float, rel_tol=1e-5)
                )
            )
            if (
                not isinstance(raw_value, (int, float))
                or isinstance(raw_value, bool)
                or not math.isfinite(raw_value)
                or is_fill
            ):
                missing += 1
                continue
            try:
                observed_at = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc)
            except ValueError as exc:
                raise ExternalServiceError("NASA POWER devolvió una fecha inválida.") from exc
            rows.append({
                "plot_id": plot_id,
                "dataset": "NASA_POWER_DAILY",
                "dataset_version": dataset_version,
                "variable": variable,
                "observed_at": observed_at,
                "value": float(raw_value),
                "unit": unit,
            })
    return rows, missing


def save_observations(session: Session, rows: list[dict]) -> int:
    """Inserta sin repetir la clave única, incluso ante solicitudes concurrentes."""
    if not rows:
        return 0

    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        insert = pg_insert
    elif dialect == "sqlite":
        insert = sqlite_insert
    else:
        raise RuntimeError(f"Dialecto de base de datos no compatible: {dialect}")
    inserted = 0
    try:
        for offset in range(0, len(rows), 500):
            batch = rows[offset:offset + 500]
            statement = insert(NasaObservation).values(batch).on_conflict_do_nothing(
                index_elements=[
                    "plot_id", "dataset", "dataset_version", "variable", "observed_at"
                ]
            )
            inserted += session.execute(statement).rowcount
        session.commit()
    except Exception:
        session.rollback()
        raise
    return inserted
