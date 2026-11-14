"""Prueba HTTP real de Uvicorn y del simulador, con SQLite y Auth ficticios."""

import asyncio
import json
from pathlib import Path
import socket
import sys
import threading

import httpx
import uvicorn

from api_test_case import IsolatedApiTest
from app.main import app


class Esp32EndToEndTests(IsolatedApiTest):
    async def test_register_simulate_and_read_over_http(self) -> None:
        await self.create_plot()  # Instala los overrides aislados de Auth y DB.
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, lifespan="off", log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            for _ in range(500):
                if server.started:
                    break
                if not thread.is_alive():
                    self.fail("Uvicorn terminó antes de iniciar.")
                await asyncio.sleep(0.01)
            self.assertTrue(server.started)
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
                response = await client.post("/api/plots", json={
                    "name": "Parcela aislada E2E", "latitude": -5, "longitude": -80,
                })
                self.assertEqual(response.status_code, 201)
                plot_id = response.json()["id"]
                for scenario, count, expected in (("riego", 10, 20), ("aire", 1, 2),
                                                   ("seco", 1, 2), ("sin_temp", 1, 1)):
                    with self.subTest(scenario=scenario):
                        external_id = f"test-e2e-{scenario}"
                        response = await client.post(f"/api/plots/{plot_id}/devices", json={
                            "external_id": external_id,
                        })
                        self.assertEqual(response.status_code, 201)
                        registration = response.json()
                        process = await asyncio.create_subprocess_exec(
                            sys.executable,
                            str(Path(__file__).resolve().parents[1] / "scripts" / "simular_esp32.py"),
                            "--url", f"http://127.0.0.1:{port}/api/devices/readings",
                            "--key", registration["secret"], "--external-id", external_id,
                            "--escenario", scenario, "--cantidad", str(count),
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                        )
                        try:
                            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
                        except asyncio.TimeoutError:
                            process.kill()
                            await process.wait()
                            raise
                        self.assertEqual(process.returncode, 0, stderr.decode())
                        self.assertEqual(json.loads(stdout), {
                            "requests": count, "inserted": expected, "already_present": 0,
                        })
                        response = await client.get(f"/api/plots/{plot_id}/sensors/readings")
                        self.assertEqual(response.status_code, 200)
                        rows = [r for r in response.json() if r["device_id"] == registration["id"]]
                        self.assertEqual(len(rows), expected)
        finally:
            server.should_exit = True
            await asyncio.to_thread(thread.join, 5)
            listener.close()
            self.assertFalse(thread.is_alive(), "Uvicorn no se detuvo.")
