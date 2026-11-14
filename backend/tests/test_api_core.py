"""CORS, errores globales y acceso privado tras reorganizar la API."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, settings
from app.core.exceptions import (
    AgroOrbitError, ConfigurationError, ExternalServiceError, ExternalServiceTimeoutError,
)
from app.database.models import Base
from app.database.session import get_db_session
from app.main import app
from app.services.auth import get_current_auth_user_id


class CorsSettingsTests(unittest.TestCase):
    def test_default_origin(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = Settings(_env_file=None)
        self.assertEqual(config.cors_origins, ["http://localhost:5173"])

    def test_origins_from_environment(self) -> None:
        with patch.dict(os.environ, {
            "CORS_ORIGINS": '["http://localhost:5173","http://192.168.1.10:5173"]',
        }, clear=True):
            config = Settings(_env_file=None)
        self.assertEqual(config.cors_origins, [
            "http://localhost:5173", "http://192.168.1.10:5173",
        ])

    def test_origins_from_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text('CORS_ORIGINS=["http://localhost:3000"]\n', encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                config = Settings(_env_file=env_file)
        self.assertEqual(config.cors_origins, ["http://localhost:3000"])

    def test_origins_must_be_a_list(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValidationError):
                Settings(cors_origins="http://localhost:5173", _env_file=None)


class CorsAndErrorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    def allowed_origin(self) -> str:
        if not settings.cors_origins:
            self.skipTest("CORS está deshabilitado en este entorno.")
        return settings.cors_origins[0]

    async def test_preflight_allows_authorization_and_json(self) -> None:
        origin = self.allowed_origin()
        response = await self.client.options("/api/plots", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], origin)
        self.assertIn("POST", response.headers["access-control-allow-methods"])
        self.assertIn("authorization", response.headers["access-control-allow-headers"])

    async def test_disallowed_origin_has_no_permission_header(self) -> None:
        origin = "https://untrusted.invalid"
        self.assertNotIn(origin, settings.cors_origins)
        response = await self.client.options("/api/plots", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
        })
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    async def test_allowed_origin_receives_cors_on_normal_response(self) -> None:
        origin = self.allowed_origin()
        response = await self.client.get("/health", headers={"Origin": origin})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], origin)

    async def test_global_errors_preserve_status_detail_and_log(self) -> None:
        cases = [
            (AgroOrbitError("Conflicto controlado", status_code=409), 409),
            (ConfigurationError("Configuración no disponible"), 500),
            (ExternalServiceError("Servicio no disponible"), 502),
            (ExternalServiceError("Servicio ocupado", status_code=503), 503),
            (ExternalServiceTimeoutError("Tiempo agotado"), 504),
        ]
        for error, expected_status in cases:
            with self.subTest(error=type(error).__name__, status=expected_status):
                with patch("app.api.routes.nasa.get_daily_power_data", new_callable=AsyncMock) as fetch:
                    fetch.side_effect = error
                    with self.assertLogs("app.main", level="ERROR") as logs:
                        response = await self.client.get(
                            "/api/nasa/power?latitude=-5&longitude=-80"
                            "&start_date=20240101&end_date=20240101"
                        )
                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(response.json(), {"detail": str(error)})
                self.assertIn("GET /api/nasa/power", logs.output[0])
                self.assertIn(str(error), logs.output[0])

    async def test_handled_error_includes_cors_headers(self) -> None:
        origin = self.allowed_origin()
        with patch("app.api.routes.nasa.get_daily_power_data", new_callable=AsyncMock) as fetch:
            fetch.side_effect = ExternalServiceError("NASA no disponible")
            with self.assertLogs("app.main", level="ERROR"):
                response = await self.client.get(
                    "/api/nasa/power?latitude=-5&longitude=-80"
                    "&start_date=20240101&end_date=20240101",
                    headers={"Origin": origin},
                )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.headers["access-control-allow-origin"], origin)


class PrivateCoreFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)
        self.identity = uuid4()

        def session_override():
            with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db_session] = session_override
        app.dependency_overrides[get_current_auth_user_id] = lambda: self.identity
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )
        await self.client.post("/api/users/me", json={"display_name": "Ana"})
        response = await self.client.post("/api/plots", json={
            "name": "Parcela norte", "latitude": -5, "longitude": -80,
        })
        self.assertEqual(response.status_code, 201, response.text)
        self.plot_id = response.json()["id"]

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        self.engine.dispose()

    async def test_private_routes_still_require_bearer(self) -> None:
        del app.dependency_overrides[get_current_auth_user_id]
        paths = [
            "/api/users/me", "/api/plots", f"/api/plots/{self.plot_id}",
            f"/api/plots/{self.plot_id}/nasa/observations",
        ]
        for path in paths:
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status_code, 401)

    async def test_observation_read_hides_other_and_missing_plots(self) -> None:
        self.identity = uuid4()
        for plot_id in (self.plot_id, str(uuid4())):
            with self.subTest(plot_id=plot_id):
                response = await self.client.get(f"/api/plots/{plot_id}/nasa/observations")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), {"detail": "Parcela no encontrada."})

    async def test_private_power_error_uses_global_handler(self) -> None:
        with patch(
            "app.api.routes.plot_nasa.power_service.get_daily_payload", new_callable=AsyncMock,
        ) as fetch:
            fetch.side_effect = ExternalServiceTimeoutError("Tiempo agotado")
            with self.assertLogs("app.main", level="ERROR"):
                response = await self.client.post(
                    f"/api/plots/{self.plot_id}/nasa/power"
                    "?start_date=20240101&end_date=20240101"
                )
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json(), {"detail": "Tiempo agotado"})
