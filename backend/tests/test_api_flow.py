"""Flujo de identidad, parcela y NASA con SQLite y POWER simulado."""

import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import Base
from app.database.session import get_db_session
from app.main import app
from app.services.auth import AuthSettings, get_current_auth_user_id


class AuthTest(unittest.IsolatedAsyncioTestCase):
    async def test_identity_comes_from_verified_auth_response(self) -> None:
        expected_id = uuid4()

        def answer(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["authorization"], "Bearer test-token")
            self.assertEqual(request.headers["apikey"], "test-key")
            return httpx.Response(200, json={"id": str(expected_id)})

        client = httpx.AsyncClient(transport=httpx.MockTransport(answer))
        config = AuthSettings(
            supabase_url="https://example.supabase.co",
            supabase_publishable_key="test-key",
            _env_file=None,
        )
        with patch("app.services.auth.auth_settings", config):
            with patch("app.services.auth.httpx.AsyncClient", return_value=client):
                actual_id = await get_current_auth_user_id(
                    HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token")
                )
        self.assertEqual(actual_id, expected_id)

    async def test_missing_token_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as error:
            await get_current_auth_user_id(None)
        self.assertEqual(error.exception.status_code, 401)


class ApiFlowTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)
        self.identity = uuid4()
        self.owner_identity = self.identity

        def session_override():
            with self.session_factory() as session:
                yield session

        def auth_override():
            return self.identity

        app.dependency_overrides[get_db_session] = session_override
        app.dependency_overrides[get_current_auth_user_id] = auth_override
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        self.engine.dispose()

    async def test_owner_and_idempotent_power_flow(self) -> None:
        user = await self.client.post("/api/users/me", json={"display_name": "Ana"})
        self.assertEqual(user.status_code, 200, user.text)
        plot = await self.client.post(
            "/api/plots",
            json={
                "name": "Parcela norte", "latitude": -5.0, "longitude": -80.6,
                "user_id": str(uuid4()),
            },
        )
        self.assertEqual(plot.status_code, 201, plot.text)
        plot_id = plot.json()["id"]
        self.assertEqual(plot.json()["user_id"], user.json()["id"])

        self.identity = uuid4()
        other = await self.client.get(f"/api/plots/{plot_id}")
        self.assertEqual(other.status_code, 404)
        self.identity = uuid4()
        self.assertEqual((await self.client.get("/api/plots")).json(), [])

        # La identidad de Auth no es el ID interno de app_user.
        self.identity = self.owner_identity

        payload = {
            "header": {"api": {"version": "v2.10.1"}, "fill_value": -999},
            "parameters": {"T2M": {"units": "C"}, "PRECTOTCORR": {"units": "mm/day"}},
            "properties": {"parameter": {
                "T2M": {"20240101": 27.5, "20240102": -999},
                "PRECTOTCORR": {"20240101": 0},
            }},
        }
        url = f"/api/plots/{plot_id}/nasa/power?start_date=20240101&end_date=20240102"
        with patch(
            "app.api.routes.plot_nasa.power_service.get_daily_payload",
            new_callable=AsyncMock,
        ) as fetch:
            fetch.return_value = payload
            first = await self.client.post(url)
            second = await self.client.post(url)

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["inserted"], 2)
        self.assertEqual(first.json()["missing_skipped"], 1)
        self.assertEqual(second.json()["inserted"], 0)
        self.assertEqual(second.json()["already_present"], 2)
        observations = await self.client.get(f"/api/plots/{plot_id}/nasa/observations")
        self.assertEqual(observations.status_code, 200, observations.text)
        self.assertEqual(len(observations.json()), 2)
        self.assertEqual(
            {item["unit"] for item in observations.json()}, {"C", "mm/day"}
        )

    async def test_unowned_plot_power_fetch_rejected(self) -> None:
        await self.client.post("/api/users/me", json={"display_name": "Carlos"})
        plot = await self.client.post(
            "/api/plots",
            json={"name": "Parcela privada", "latitude": -6.0, "longitude": -79.0},
        )
        self.assertEqual(plot.status_code, 201)
        plot_id = plot.json()["id"]

        # Intento de acceso desde otra identidad
        self.identity = uuid4()
        url = f"/api/plots/{plot_id}/nasa/power?start_date=20240101&end_date=20240102"
        response = await self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Parcela no encontrada.")

    async def test_float_and_nan_fill_values_are_skipped(self) -> None:
        user = await self.client.post("/api/users/me", json={"display_name": "Lucia"})
        plot = await self.client.post(
            "/api/plots",
            json={"name": "Parcela sur", "latitude": -12.0, "longitude": -77.0},
        )
        plot_id = plot.json()["id"]

        payload = {
            "header": {"api": {"version": "v2.10.1"}, "fill_value": -999.0},
            "parameters": {"T2M": {"units": "C"}},
            "properties": {"parameter": {
                "T2M": {
                    "20240101": 24.0,
                    "20240102": -999.0,
                    "20240103": float("nan"),
                    "20240104": None,
                },
            }},
        }
        url = f"/api/plots/{plot_id}/nasa/power?start_date=20240101&end_date=20240104"
        with patch(
            "app.api.routes.plot_nasa.power_service.get_daily_payload",
            new_callable=AsyncMock,
        ) as fetch:
            fetch.return_value = payload
            resp = await self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["inserted"], 1)
        self.assertEqual(resp.json()["missing_skipped"], 3)
