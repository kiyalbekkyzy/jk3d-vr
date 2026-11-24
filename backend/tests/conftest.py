import os
import tempfile

# Test settings must be set before the app is imported.
_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}/test.db"))
os.environ["API_KEY"] = "test-key"
os.environ["LLM_PROVIDER"] = "template"
os.environ["TTS_PROVIDER"] = "silent"
os.environ["AUDIO_DIR"] = f"{_tmp}/audio"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

AUTH = {"X-API-Key": "test-key"}


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def approved_project(client):
    """Pilot apartment with a small approved passport and designer key points."""
    client.post("/v1/projects", headers=AUTH, json={"id": "jk3d-001", "name": "Pilot apartment", "floor": 9})
    client.put("/v1/projects/jk3d-001/passport", headers=AUTH, json={"fields": [
        {"key": "living.area_m2", "room": "LIVING", "label": {"ru": "Площадь", "en": "Area"},
         "value": "18.4", "unit": "m2", "required": True, "status": "ok"},
        {"key": "living.ceiling_m", "room": "LIVING", "label": {"ru": "Высота потолка", "en": "Ceiling height"},
         "value": "2.89", "unit": "m", "required": True, "status": "ok"},
        {"key": "bedroom.area_m2", "room": "BEDROOM", "label": {"ru": "Площадь", "en": "Area"},
         "value": "12.1", "unit": "m2", "status": "ok"},
    ]})
    client.put("/v1/projects/jk3d-001/key-points", headers=AUTH, json={"key_points": [
        {"room": "LIVING", "lang": "ru", "text": "Кухня объединена с гостиной по просьбе клиента"},
        {"room": "LIVING", "lang": "en", "text": "The kitchen is joined with the living room at the client's request"},
    ]})
    r = client.post("/v1/projects/jk3d-001/approve", headers=AUTH)
    assert r.status_code == 200
    return "jk3d-001"
