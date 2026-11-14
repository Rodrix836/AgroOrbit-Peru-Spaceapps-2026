"""Envía mediciones ficticias para probar la API; no calibra sensores reales."""

import argparse
from datetime import datetime, timedelta, timezone
import json

import httpx


def sample(external_id: str, scenario: str, index: int, observed_at: datetime) -> dict:
    if scenario == "aire":
        raw, calibrated, flag = 2924, 0.0, "clamped_dry"
    elif scenario in ("seco", "sin_temp"):
        raw, calibrated, flag = 2750, 10.0, "ok"
    else:
        # Pares sintéticos para probar el transporte, sin valor de calibración.
        raw, calibrated = max(1400, 2800 - index * 100), min(100.0, index * 10.0)
        flag = "clamped_wet" if calibrated == 100 else "ok"
    readings = [{
        "variable": "soil_moisture", "raw_value": raw, "calibrated_value": calibrated,
        "unit": "%", "quality_flag": flag,
    }]
    if scenario != "sin_temp":
        temperature = round(30.12 + (index % 5) * 0.2, 2)
        readings.append({
            "variable": "soil_temperature", "raw_value": temperature,
            "calibrated_value": temperature, "unit": "°C", "quality_flag": "ok",
        })
    return {"external_id": external_id, "observed_at": observed_at.isoformat(), "readings": readings}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--external-id", required=True)
    parser.add_argument("--escenario", choices=("aire", "seco", "riego", "sin_temp"), default="riego")
    parser.add_argument("--cantidad", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.cantidad <= 1000:
        parser.error("--cantidad debe estar entre 1 y 1000.")
    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=args.cantidad - 1)
    totals = {"requests": args.cantidad, "inserted": 0, "already_present": 0}
    try:
        with httpx.Client(timeout=10) as client:
            for index in range(args.cantidad):
                response = client.post(
                    args.url, headers={"X-Device-Key": args.key},
                    json=sample(args.external_id, args.escenario, index, start + timedelta(seconds=index)),
                )
                response.raise_for_status()
                if response.status_code != 201:
                    raise ValueError(f"Se esperaba HTTP 201; se recibió {response.status_code}.")
                result = response.json()
                totals["inserted"] += result["inserted"]
                totals["already_present"] += result["already_present"]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        # Nunca mostrar la clave ni los encabezados de la petición.
        parser.exit(1, f"No se completó la simulación: {exc}\n")
    print(json.dumps(totals))


if __name__ == "__main__":
    main()
