"""Pruebas básicas de configuración y continuidad de la API."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from pydantic import ValidationError

from app.core.config import (
    POWER_BASE_URL,
    POWER_COMMUNITY,
    POWER_PARAMETERS,
    POWER_TIMEOUT_SECONDS,
    Settings,
)
from app.core.exceptions import ExternalServiceError, ExternalServiceTimeoutError
from app.main import app
from app.services.nasa.power_service import PowerService


class SettingsTests(unittest.TestCase):
    def test_defaults_without_env_file(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = Settings(_env_file=None)

        self.assertEqual(config.app_name, "AgroOrbit Perú API")
        self.assertEqual(config.app_env, "development")
        self.assertTrue(config.debug)
        self.assertEqual(config.nasa_power_community, "AG")
        self.assertEqual(config.nasa_power_timeout, 30)
        self.assertTrue(config.nasa_power_base_url.startswith("https://"))
        self.assertEqual(len(POWER_PARAMETERS), 7)

    def test_backwards_compatibility_constants(self) -> None:
        self.assertEqual(POWER_COMMUNITY, "AG")
        self.assertEqual(POWER_TIMEOUT_SECONDS, 30)
        self.assertTrue(POWER_BASE_URL.startswith("https://"))

    def test_environment_overrides(self) -> None:
        with patch.dict(
            os.environ,
            {"NASA_POWER_TIMEOUT": "12.5", "NASA_POWER_COMMUNITY": "SB", "DEBUG": "false"},
            clear=True,
        ):
            config = Settings(_env_file=None)

        self.assertEqual(config.nasa_power_timeout, 12.5)
        self.assertEqual(config.nasa_power_community, "SB")
        self.assertFalse(config.debug)

    def test_dotenv_file_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("NASA_POWER_TIMEOUT=18\nAPP_ENV=testing\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                config = Settings(_env_file=env_file)

        self.assertEqual(config.nasa_power_timeout, 18)
        self.assertEqual(config.app_env, "testing")

    def test_timeout_must_be_positive(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValidationError):
                Settings(nasa_power_timeout=0, _env_file=None)


class PowerServiceUnitTests(unittest.TestCase):
    def test_extract_upstream_error_with_list_detail(self) -> None:
        response = httpx.Response(
            422,
            json={"detail": [{"loc": ["query", "latitude"], "msg": "Input should be >= -90"}]},
        )
        msg = PowerService._extract_upstream_error(response)
        self.assertIn("Input should be >= -90", msg)

    def test_extract_upstream_error_with_messages(self) -> None:
        response = httpx.Response(
            422,
            json={"messages": ["Fecha inicial posterior a final"]},
        )
        msg = PowerService._extract_upstream_error(response)
        self.assertEqual(msg, "Fecha inicial posterior a final")


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_health(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    async def test_root(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["project"], "AgroOrbit Perú")

    async def test_docs(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        self.assertEqual(response.status_code, 200)

    async def test_power_route_keeps_response_shape(self) -> None:
        sample = {"T2M": {"20240101": 27.68}}
        with patch(
            "app.api.routes.nasa.get_daily_power_data", new_callable=AsyncMock
        ) as get_data:
            get_data.return_value = sample
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/nasa/power",
                    params={
                        "latitude": -5.0,
                        "longitude": -80.6,
                        "start_date": "20240101",
                        "end_date": "20240101",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], sample)
        get_data.assert_awaited_once_with(-5.0, -80.6, "20240101", "20240101")

    async def test_power_timeout_returns_504(self) -> None:
        with patch(
            "app.api.routes.nasa.get_daily_power_data", new_callable=AsyncMock
        ) as get_data:
            get_data.side_effect = ExternalServiceTimeoutError("Tiempo agotado")
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/nasa/power?latitude=-5&longitude=-80.6"
                    "&start_date=20240101&end_date=20240101"
                )

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["detail"], "Tiempo agotado")
        self.assertIsInstance(get_data.side_effect, ExternalServiceError)
