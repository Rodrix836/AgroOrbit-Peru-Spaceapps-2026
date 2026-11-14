"""Campañas con cultivos ficticios y autenticación simulada."""

from unittest.mock import patch
from uuid import uuid4

from api_test_case import IsolatedApiTest
from app.database.models import Crop
from app.main import app
from app.services.auth import get_current_auth_user_id


class CropCycleApiTests(IsolatedApiTest):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.plot_id = await self.create_plot()
        with self.sessions() as session:
            crop = Crop(code="test_crop", name="Cultivo ficticio de prueba")
            inactive = Crop(code="test_inactive", name="Inactivo de prueba", is_active=False)
            session.add_all([crop, inactive])
            session.commit()
            self.crop_id, self.inactive_id = str(crop.id), str(inactive.id)
        self.url = f"/api/plots/{self.plot_id}/crop-cycles"

    def body(self, **changes):
        return {"crop_id": self.crop_id, "sowing_date": "2026-01-01", "status": "active", **changes}

    async def test_finish_then_start_another_active_cycle(self) -> None:
        response = await self.client.post(self.url, json=self.body())
        self.assertEqual(response.status_code, 201, response.text)
        first = response.json()
        self.assertEqual(first["origin"], "farmer")
        self.assertEqual(first["crop_code"], "test_crop")
        self.assertEqual((await self.client.post(self.url, json=self.body())).status_code, 409)
        response = await self.client.patch(f"{self.url}/{first['id']}", json={
            "status": "finished", "harvest_date": "2026-03-01",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((await self.client.post(self.url, json=self.body(sowing_date="2026-04-01"))).status_code, 201)
        history = (await self.client.get(self.url)).json()
        self.assertEqual([row["sowing_date"] for row in history], ["2026-04-01", "2026-01-01"])
        self.assertEqual(history[0]["crop_name"], "Cultivo ficticio de prueba")

    async def test_invalid_creation_dates_status_and_origin(self) -> None:
        for body in (
            self.body(harvest_date="2025-12-31"), self.body(status="finished"),
            self.body(origin="recommendation"), self.body(status="unknown"),
        ):
            with self.subTest(body=body):
                self.assertEqual((await self.client.post(self.url, json=body)).status_code, 422)

    async def test_missing_or_inactive_crop(self) -> None:
        for crop_id in (str(uuid4()), self.inactive_id):
            response = await self.client.post(self.url, json=self.body(crop_id=crop_id))
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail": "Cultivo no encontrado."})

    async def test_unowned_plot_and_wrong_plot_cycle(self) -> None:
        cycle = (await self.client.post(self.url, json=self.body())).json()
        second_plot = await self.create_plot()
        response = await self.client.patch(
            f"/api/plots/{second_plot}/crop-cycles/{cycle['id']}", json={"status": "planned"},
        )
        self.assertEqual(response.status_code, 404)
        self.identity = uuid4()
        responses = [
            await self.client.get(self.url),
            await self.client.post(self.url, json=self.body()),
            await self.client.patch(f"{self.url}/{cycle['id']}", json={"status": "planned"}),
        ]
        for response in responses:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail": "Parcela no encontrada."})

    async def test_patch_validates_resulting_state_and_partial_updates(self) -> None:
        cycle = (await self.client.post(self.url, json=self.body())).json()
        url = f"{self.url}/{cycle['id']}"
        for body in ({"status": "finished"}, {"harvest_date": "2025-01-01"},
                     {"origin": "recommendation"}, {"status": None}, {}):
            self.assertEqual((await self.client.patch(url, json=body)).status_code, 422)
        self.assertEqual((await self.client.patch(url, json={"harvest_date": "2026-03-01"})).status_code, 200)
        self.assertEqual((await self.client.patch(url, json={"status": "finished"})).status_code, 200)
        self.assertEqual((await self.client.patch(url, json={"harvest_date": None})).status_code, 422)
        response = await self.client.patch(url, json={"status": "planned", "harvest_date": None})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["harvest_date"])

    async def test_activation_conflict_and_self_update(self) -> None:
        active = (await self.client.post(self.url, json=self.body())).json()
        planned = (await self.client.post(self.url, json=self.body(status="planned"))).json()
        response = await self.client.patch(f"{self.url}/{planned['id']}", json={"status": "active"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"detail": "La parcela ya tiene una campaña activa."})
        response = await self.client.patch(f"{self.url}/{active['id']}", json={"status": "active"})
        self.assertEqual(response.status_code, 200)

    async def test_unique_index_conflict_rolls_back_after_racing_precheck(self) -> None:
        await self.client.post(self.url, json=self.body())
        planned = (await self.client.post(self.url, json=self.body(status="planned"))).json()
        with patch("app.api.routes.crop_cycles.active_cycle", return_value=False):
            create = await self.client.post(self.url, json=self.body())
            update = await self.client.patch(f"{self.url}/{planned['id']}", json={"status": "active"})
        self.assertEqual(create.status_code, 409, create.text)
        self.assertEqual(update.status_code, 409, update.text)
        history = (await self.client.get(self.url)).json()
        self.assertEqual(sorted(row["status"] for row in history), ["active", "planned"])

    async def test_empty_history_and_missing_cycle(self) -> None:
        self.assertEqual((await self.client.get(self.url)).json(), [])
        response = await self.client.patch(f"{self.url}/{uuid4()}", json={"status": "planned"})
        self.assertEqual(response.status_code, 404)

    async def test_routes_require_authentication(self) -> None:
        del app.dependency_overrides[get_current_auth_user_id]
        responses = [
            await self.client.get(self.url),
            await self.client.post(self.url, json=self.body()),
            await self.client.patch(f"{self.url}/{uuid4()}", json={"status": "planned"}),
        ]
        for response in responses:
            self.assertEqual(response.status_code, 401)
