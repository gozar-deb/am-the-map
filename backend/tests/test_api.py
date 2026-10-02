from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test_am_the_map.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_root_and_status():
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "Am the Map" in r.json()["name"]

        r2 = client.get("/api/status")
        assert r2.status_code == 200
        assert r2.json()["acquisition_mode"] == "simulated"


def test_doctor_endpoint():
    with TestClient(app) as client:
        r = client.get("/api/system/doctor")
        assert r.status_code == 200
        assert "dependencies" in r.json()


def test_ai_status_defaults_to_offline_privacy_on():
    with TestClient(app) as client:
        r = client.get("/api/ai/status")
        data = r.json()
        assert data["privacy_mode"] is True
        assert data["external_ai_allowed"] is False


def test_dataset_lifecycle(tmp_path):
    with TestClient(app) as client:
        r = client.post("/api/datasets", json={"name": "unit-test-ds", "description": "test"})
        assert r.status_code == 200
        r2 = client.get("/api/datasets/unit-test-ds")
        assert r2.status_code == 200
        assert "csi" in r2.json()["file_counts"]
