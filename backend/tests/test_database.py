"""Contrato mínimo de persistencia, sin depender de Supabase ni de la red."""

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.connection import normalize_database_url
from app.database.models import Base, NasaObservation, Plot


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
            plot = Plot(name="Parcela Norte", latitude=Decimal("-5.0"), longitude=Decimal("-80.6"))
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
            plot = Plot(name="Parcela Norte", latitude=-5, longitude=-80.6)
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
            session.add(Plot(name="Inválida", latitude=91, longitude=-80.6))
            with self.assertRaises(IntegrityError):
                session.commit()


if __name__ == "__main__":
    unittest.main()
