"""Contrato mínimo de persistencia, sin depender de Supabase ni de la red."""

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.connection import normalize_database_url
from app.database.models import (
    AgronomicSource, AppUser, Base, Crop, CropCycle, CropRequirement,
    Device, Indicator, NasaObservation, Plot, Recommendation,
    RecommendationItem, RotationPlan, RotationRule, SensorReading,
)


class DatabaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_supabase_url_uses_psycopg_driver(self) -> None:
        url = normalize_database_url(
            "postgresql://postgres:secret@db.example.supabase.co:5432/postgres"
        )
        self.assertEqual(url.drivername, "postgresql+psycopg")
        self.assertEqual(url.host, "db.example.supabase.co")

    def test_plot_and_observation_round_trip(self) -> None:
        with Session(self.engine) as session:
            user = AppUser(display_name="Agricultora de prueba")
            plot = Plot(user=user, name="Parcela Norte", latitude=Decimal("-5.0"), longitude=Decimal("-80.6"))
            observation = NasaObservation(
                plot=plot,
                dataset="NASA_POWER",
                dataset_version="unspecified",
                variable="T2M",
                observed_at=datetime(2026, 10, 28, tzinfo=timezone.utc),
                value=27.5,
                unit="°C",
            )
            session.add(observation)
            session.commit()

            stored = session.scalars(select(NasaObservation)).one()
            self.assertEqual(stored.plot_id, plot.id)
            self.assertEqual(stored.plot.name, "Parcela Norte")
            self.assertEqual(stored.variable, "T2M")

    def test_rejects_duplicate_observation(self) -> None:
        with Session(self.engine) as session:
            user = AppUser(display_name="Agricultora de prueba")
            plot = Plot(user=user, name="Parcela Norte", latitude=-5, longitude=-80.6)
            session.add(plot)
            session.flush()
            values = dict(
                plot_id=plot.id,
                dataset="NASA_POWER",
                dataset_version="unspecified",
                variable="T2M",
                observed_at=datetime(2026, 10, 28, tzinfo=timezone.utc),
                value=27.5,
                unit="°C",
            )
            session.add_all([NasaObservation(**values), NasaObservation(**values)])
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_rejects_out_of_range_coordinates(self) -> None:
        with Session(self.engine) as session:
            user = AppUser(display_name="Agricultora de prueba")
            session.add(Plot(user=user, name="Inválida", latitude=91, longitude=-80.6))
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_full_parcel_lifecycle(self) -> None:
        """Catálogo con fuente, campaña, IoT y decisión quedan vinculados."""
        with Session(self.engine) as session:
            user = AppUser(display_name="Productora de prueba")
            source = AgronomicSource(citation="Fuente técnica de prueba")
            session.add_all([user, source])
            session.flush()
            crop = Crop(code="frijol_test", name="Frijol de prueba", cycle_min_days=60,
                        cycle_max_days=90, cycle_source_id=source.id)
            session.add(crop)
            session.flush()
            plot = Plot(user_id=user.id, name="Parcela de prueba", latitude=-5,
                        longitude=-80.6, declared_irrigated=True)
            session.add(plot)
            session.flush()
            session.add_all([
                CropRequirement(crop_id=crop.id, criterion="temperature",
                                value={"min": 18, "max": 30}, unit="°C",
                                source_id=source.id, evidence_level="A"),
                RotationRule(rule_kind="same_crop", effect="penalty", weight=Decimal("0.2"),
                             rationale="Regla de prueba", source_id=source.id,
                             evidence_level="A"),
                CropCycle(plot_id=plot.id, crop_id=crop.id, sowing_date=date(2026, 10, 1),
                          status="active", origin="farmer"),
                Indicator(plot_id=plot.id, name="rainfall_30d", value_numeric=Decimal("12"),
                          unit="mm", window_start=datetime(2026, 9, 1, tzinfo=timezone.utc),
                          window_end=datetime(2026, 10, 1, tzinfo=timezone.utc),
                          calculation_version="test-v1", source_refs=[]),
            ])
            device = Device(plot_id=plot.id, external_id="esp32-test")
            session.add(device)
            session.flush()
            session.add(SensorReading(device_id=device.id,
                                      observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                                      variable="soil_moisture", raw_value=Decimal("23"),
                                      unit="%"))
            recommendation = Recommendation(plot_id=plot.id, horizon_days=90,
                                            priority="save_water", engine_version="test-v1",
                                            status="ready", confidence="medium",
                                            recommended_crop_id=crop.id,
                                            input_snapshot={"plot_id": str(plot.id)})
            session.add(recommendation)
            session.flush()
            session.add_all([
                RecommendationItem(recommendation_id=recommendation.id, crop_id=crop.id,
                                   rank=1, score=Decimal("0.75"), eligible=True,
                                   reasons=["Motivo de prueba"], limiting_factors=[]),
                RotationPlan(recommendation_id=recommendation.id, step=1, action="crop",
                             crop_id=crop.id, start_on=date(2026, 11, 1),
                             end_on=date(2027, 1, 31), climate_basis="historical",
                             confidence="medium"),
            ])
            session.commit()
            self.assertEqual(session.scalar(select(RecommendationItem).join(Recommendation).where(
                Recommendation.plot_id == plot.id)).rank, 1)
            self.assertEqual(session.scalar(select(SensorReading)).device_id, device.id)

    def test_rejects_two_active_cycles_for_one_plot(self) -> None:
        with Session(self.engine) as session:
            user = AppUser(display_name="Productora de prueba")
            crop = Crop(code="test", name="Cultivo de prueba")
            plot = Plot(user=user, name="Parcela de prueba", latitude=-5, longitude=-80.6)
            session.add_all([user, crop, plot])
            session.flush()
            for start in (date(2026, 1, 1), date(2026, 2, 1)):
                session.add(CropCycle(plot_id=plot.id, crop_id=crop.id,
                                      sowing_date=start, status="active", origin="farmer"))
            with self.assertRaises(IntegrityError):
                session.commit()


if __name__ == "__main__":
    unittest.main()
