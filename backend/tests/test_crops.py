"""Catálogo público con datos ficticios en SQLite en memoria."""

from uuid import uuid4

from sqlalchemy import event

from api_test_case import IsolatedApiTest
from app.database.models import AgronomicSource, Crop, CropRequirement


class CropApiTests(IsolatedApiTest):
    async def test_empty_catalog_is_public(self) -> None:
        response = await self.client.get("/api/crops")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    async def test_list_is_ordered_and_excludes_inactive(self) -> None:
        with self.sessions() as session:
            session.add_all([
                Crop(code="test_z", name="Z de prueba"),
                Crop(code="test_a", name="A de prueba"),
                Crop(code="test_hidden", name="Inactivo de prueba", is_active=False),
            ])
            session.commit()
        response = await self.client.get("/api/crops")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["code"] for row in response.json()], ["test_a", "test_z"])
        self.assertEqual(set(response.json()[0]), {
            "id", "code", "name", "scientific_name", "botanical_family",
            "functional_group", "is_perennial", "cycle_min_days", "cycle_max_days",
        })

    async def test_detail_preserves_json_and_loads_sources_in_batches(self) -> None:
        value = {"min": 1, "nested": {"values": [2, None, "prueba"]}}
        with self.sessions() as session:
            source = AgronomicSource(citation="Fuente ficticia de prueba", publisher="Prueba",
                                     url="https://example.invalid/test", publication_year=2026)
            session.add(source)
            session.flush()
            crop = Crop(code="test_crop", name="Cultivo de prueba", cycle_min_days=10,
                        cycle_max_days=20, cycle_source_id=source.id)
            session.add(crop)
            session.flush()
            crop_id = str(crop.id)
            for index in range(8):
                session.add(CropRequirement(crop_id=crop.id, criterion=f"test_{index}",
                                           value=value, unit="test", source_id=source.id,
                                           evidence_level="C", notes="Solo prueba"))
            session.commit()
        queries = []

        def record_query(*args):
            queries.append(args[2])

        event.listen(self.engine, "before_cursor_execute", record_query)
        try:
            response = await self.client.get(f"/api/crops/{crop_id}")
        finally:
            event.remove(self.engine, "before_cursor_execute", record_query)
        self.assertEqual(response.status_code, 200, response.text)
        detail = response.json()
        self.assertEqual(len(detail["requirements"]), 8)
        self.assertEqual(detail["requirements"][0]["value"], value)
        self.assertEqual(detail["requirements"][0]["source"], detail["cycle_source"])
        self.assertEqual(detail["cycle_source"]["citation"], "Fuente ficticia de prueba")
        self.assertLessEqual(len(queries), 4)

    async def test_missing_and_inactive_crop_have_same_404(self) -> None:
        with self.sessions() as session:
            crop = Crop(code="test_inactive", name="Inactivo de prueba", is_active=False)
            session.add(crop)
            session.commit()
            inactive_id = str(crop.id)
        for crop_id in (str(uuid4()), inactive_id):
            response = await self.client.get(f"/api/crops/{crop_id}")
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail": "Cultivo no encontrado."})

    async def test_detail_without_optional_sources_or_requirements(self) -> None:
        with self.sessions() as session:
            crop = Crop(code="test_empty", name="Sin requisitos de prueba")
            session.add(crop)
            session.commit()
            crop_id = str(crop.id)
        response = await self.client.get(f"/api/crops/{crop_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["requirements"], [])
        self.assertIsNone(response.json()["cycle_source"])
