"""Infraestructura de pruebas aislada de PostgreSQL y Supabase reales."""

import unittest
from uuid import uuid4

import httpx
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import Base
from app.database.session import get_db_session
from app.main import app
from app.services.auth import get_current_auth_user_id


class IsolatedApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.identity = uuid4()

        def session_override():
            with self.sessions() as session:
                yield session

        app.dependency_overrides[get_db_session] = session_override
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        self.engine.dispose()

    async def create_plot(self) -> str:
        app.dependency_overrides[get_current_auth_user_id] = lambda: self.identity
        response = await self.client.post("/api/users/me", json={"display_name": "Usuario de prueba"})
        self.assertEqual(response.status_code, 200, response.text)
        response = await self.client.post("/api/plots", json={
            "name": "Parcela de prueba", "latitude": -5, "longitude": -80,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]
