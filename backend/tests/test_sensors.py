"""Kit ficticio con SQLite en memoria; no usa hardware ni Supabase real."""

from datetime import datetime, timedelta, timezone
import hashlib
from unittest.mock import patch
from uuid import UUID, uuid4

from api_test_case import IsolatedApiTest
from app.database.models import Device, SensorReading
from app.main import app
from app.services.auth import get_current_auth_user_id
from sqlalchemy import func, select


class SensorApiTests(IsolatedApiTest):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.plot_id = await self.create_plot()
        self.device_url = f"/api/plots/{self.plot_id}/devices"
        self.history_url = f"/api/plots/{self.plot_id}/sensors/readings"
        response = await self.client.post(self.device_url, json={"external_id": "test-kit"})
        self.assertEqual(response.status_code, 201, response.text)
        self.registration = response.json()
        self.headers = {"X-Device-Key": self.registration["secret"]}

    def body(self, *, observed_at="2026-01-01T00:00:00Z", only_moisture=False):
        readings = [{"variable": "soil_moisture", "raw_value": 2924,
                     "calibrated_value": 0.0, "unit": "%", "quality_flag": "clamped_dry"}]
        if not only_moisture:
            readings.append({"variable": "soil_temperature", "raw_value": 30.12,
                             "calibrated_value": 30.12, "unit": "°C", "quality_flag": "ok"})
        result = {"external_id": "test-kit", "readings": readings}
        if observed_at is not None:
            result["observed_at"] = observed_at
        return result

    async def send(self, body):
        return await self.client.post("/api/devices/readings", json=body, headers=self.headers)

    async def test_secret_only_returned_at_registration_and_hash_stored(self) -> None:
        secret = self.registration["secret"]
        self.assertGreaterEqual(len(secret), 43)
        self.assertNotIn("secret_hash", self.registration)
        response = await self.client.get(self.device_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("secret", response.json()[0])
        self.assertNotIn("secret_hash", response.json()[0])
        with self.sessions() as session:
            device = session.get(Device, UUID(self.registration["id"]))
            self.assertEqual(device.secret_hash, hashlib.sha256(secret.encode()).hexdigest())
        duplicate = await self.client.post(self.device_url, json={"external_id": "test-kit"})
        self.assertEqual(duplicate.status_code, 409)
        self.assertNotIn(secret, duplicate.text)

    async def test_two_variables_idempotent_and_moisture_only(self) -> None:
        # La ingesta no usa Bearer, aunque el registro sí lo requiere.
        del app.dependency_overrides[get_current_auth_user_id]
        response = await self.send(self.body())
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json(), {"inserted": 2, "already_present": 0})
        response = await self.send(self.body(observed_at="2025-12-31T19:00:00-05:00"))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"inserted": 0, "already_present": 2})
        response = await self.send(self.body(observed_at="2026-01-02T00:00:00Z", only_moisture=True))
        self.assertEqual(response.json(), {"inserted": 1, "already_present": 0})
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(SensorReading)), 3)

    async def test_partial_duplicate_counts_per_variable(self) -> None:
        await self.send(self.body(only_moisture=True))
        response = await self.send(self.body())
        self.assertEqual(response.json(), {"inserted": 1, "already_present": 1})

    async def test_invalid_readings(self) -> None:
        cases = [
            (0, "raw_value", -1), (0, "raw_value", 4096), (0, "raw_value", 2924.5),
            (0, "raw_value", True), (0, "calibrated_value", -0.1),
            (0, "calibrated_value", 100.1), (0, "unit", "ADC"),
            (0, "quality_flag", "unknown"), (1, "unit", "C"),
            (1, "raw_value", -127), (1, "raw_value", 85), (1, "raw_value", -10.1),
            (1, "calibrated_value", -127), (1, "calibrated_value", 85),
            (1, "calibrated_value", 70.1), (1, "variable", "unknown"),
        ]
        for index, field, value in cases:
            with self.subTest(field=field, value=value):
                body = self.body()
                body["readings"][index][field] = value
                self.assertEqual((await self.send(body)).status_code, 422)
        for readings in ([], [self.body()["readings"][0]] * 2):
            body = self.body()
            body["readings"] = readings
            self.assertEqual((await self.send(body)).status_code, 422)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(SensorReading)), 0)

    async def test_sensor_boundaries_and_clamped_flags_are_saved(self) -> None:
        for index, (raw, calibrated, flag, temperature) in enumerate([
            (0, 100, "clamped_wet", -10), (4095, 0, "clamped_dry", 70),
        ]):
            body = self.body(observed_at=f"2026-01-0{index + 1}T00:00:00Z")
            body["readings"][0].update(raw_value=raw, calibrated_value=calibrated, quality_flag=flag)
            body["readings"][1].update(raw_value=temperature, calibrated_value=temperature)
            self.assertEqual((await self.send(body)).status_code, 201)
        rows = (await self.client.get(self.history_url)).json()
        self.assertEqual({row["quality_flag"] for row in rows}, {"ok", "clamped_wet", "clamped_dry"})

    async def test_invalid_keys_unknown_inactive_and_missing_secret_have_same_401(self) -> None:
        responses = [
            await self.client.post("/api/devices/readings", json=self.body()),
            await self.client.post("/api/devices/readings", json=self.body(), headers={"X-Device-Key": "wrong"}),
        ]
        body = self.body()
        body["external_id"] = "test-unknown"
        responses.append(await self.send(body))
        with self.sessions() as session:
            device = session.get(Device, UUID(self.registration["id"]))
            device.status = "inactive"
            session.commit()
        responses.append(await self.send(self.body()))
        with self.sessions() as session:
            device = session.get(Device, UUID(self.registration["id"]))
            device.status = "active"
            device.secret_hash = None
            session.commit()
        responses.append(await self.send(self.body()))
        for response in responses:
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {"detail": "Credenciales del dispositivo inválidas."})

    async def test_observation_requires_timezone_and_rejects_future(self) -> None:
        future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        for observed_at in ("2026-01-01T00:00:00", future):
            self.assertEqual((await self.send(self.body(observed_at=observed_at))).status_code, 422)

    async def test_missing_observation_uses_server_utc_to_the_second(self) -> None:
        now = datetime(2026, 1, 1, 2, 3, 4, 567890, tzinfo=timezone.utc)
        with patch("app.api.routes.sensors.datetime") as clock:
            clock.now.return_value = now
            response = await self.send(self.body(observed_at=None))
        self.assertEqual(response.status_code, 201, response.text)
        rows = (await self.client.get(self.history_url)).json()
        self.assertEqual({row["observed_at"] for row in rows}, {"2026-01-01T02:03:04Z"})

    async def test_history_filter_order_limit_and_plot_isolation(self) -> None:
        await self.send(self.body())
        await self.send(self.body(observed_at="2026-01-02T00:00:00Z"))
        response = await self.client.get(self.history_url, params={"variable": "soil_moisture"})
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual([row["observed_at"] for row in rows], ["2026-01-02T00:00:00Z", "2026-01-01T00:00:00Z"])
        self.assertEqual({row["variable"] for row in rows}, {"soil_moisture"})
        self.assertEqual(len((await self.client.get(self.history_url, params={"limit": 1})).json()), 1)
        for params in ({"limit": 0}, {"limit": 1001}, {"variable": "unknown"}):
            self.assertEqual((await self.client.get(self.history_url, params=params)).status_code, 422)
        other_plot = await self.create_plot()
        self.assertEqual((await self.client.get(f"/api/plots/{other_plot}/sensors/readings")).json(), [])
        self.identity = uuid4()
        for response in (
            await self.client.get(self.device_url), await self.client.get(self.history_url),
            await self.client.post(self.device_url, json={"external_id": "test-other"}),
        ):
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail": "Parcela no encontrada."})

    async def test_private_routes_require_bearer(self) -> None:
        del app.dependency_overrides[get_current_auth_user_id]
        for response in (
            await self.client.get(self.device_url), await self.client.get(self.history_url),
            await self.client.post(self.device_url, json={"external_id": "test-other"}),
        ):
            self.assertEqual(response.status_code, 401)
