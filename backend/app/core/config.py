"""Configuración mínima de la integración con NASA POWER."""

import os

POWER_BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_COMMUNITY = "AG"
POWER_PARAMETERS = (
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "PRECTOTCORR",
    "RH2M",
    "WS10M",
    "ALLSKY_SFC_SW_DWN",
)
POWER_TIMEOUT_SECONDS = float(os.getenv("POWER_TIMEOUT_SECONDS", "30"))
