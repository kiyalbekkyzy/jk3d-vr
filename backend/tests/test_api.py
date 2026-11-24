"""API, persistence and negative-path tests (FR-11 to FR-14, NFR-06)."""
from app import speech

from .conftest import AUTH


def test_health_needs_no_key(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_requests_without_key_are_rejected(client):
    assert client.post("/v1/projects", json={"id": "x", "name": "x"}).status_code == 401
    assert client.get("/v1/projects/x", headers={"X-API-Key": "wrong"}).status_code == 401


def test_create_project_validation(client):
    r = client.post("/v1/projects", headers=AUTH, json={"id": "bad id!", "name": "x"})
    assert r.status_code == 422
    r = client.post("/v1/projects", headers=AUTH, json={"id": "p1", "name": "x", "languages": ["russian"]})
    assert r.status_code == 422


def test_duplicate_project_conflict(client):
    body = {"id": "p1", "name": "x"}
    assert client.post("/v1/projects", headers=AUTH, json=body).status_code == 201
    assert client.post("/v1/projects", headers=AUTH, json=body).status_code == 409


def test_unknown_project_404(client):
    assert client.get("/v1/projects/nope", headers=AUTH).status_code == 404


def test_approve_blocked_by_empty_required_field(client):
    client.post("/v1/projects", headers=AUTH, json={"id": "p1", "name": "x"})
    client.put("/v1/projects/p1/passport", headers=AUTH, json={"fields": [
        {"key": "address", "value": None, "required": True}]})
    r = client.post("/v1/projects/p1/approve", headers=AUTH)
    assert r.status_code == 409
    assert r.json()["detail"]["fields"] == ["address"]


def test_speech_blocked_until_approved(client):
    client.post("/v1/projects", headers=AUTH, json={"id": "p1", "name": "x"})
    assert client.post("/v1/speech", headers=AUTH, json={"project_id": "p1"}).status_code == 409


def test_passport_change_resets_approval(client, approved_project):
    client.put(f"/v1/projects/{approved_project}/passport", headers=AUTH, json={"fields": [
        {"key": "living.area_m2", "room": "LIVING", "value": "18.6", "unit": "m2", "required": True}]})
    assert client.get(f"/v1/projects/{approved_project}", headers=AUTH).json()["approved"] is False


def test_full_flow_speech_tts_export(client, approved_project):
    r = client.post("/v1/speech", headers=AUTH, json={"project_id": approved_project})
    assert r.status_code == 201, r.text
    items = r.json()
    assert {(s["room"], s["lang"]) for s in items} == {
        ("BEDROOM", "en"), ("BEDROOM", "ru"), ("LIVING", "en"), ("LIVING", "ru")}
    living_ru = next(s for s in items if s["room"] == "LIVING" and s["lang"] == "ru")
    assert "18,4 м²" in living_ru["text"] and "2,89 м" in living_ru["text"]
    assert "объединена с гостиной" in living_ru["text"]
    assert living_ru["fact_check"]["passed"] is True

    # Draft speech cannot be voiced.
    assert client.post("/v1/tts", headers=AUTH, json={"speech_id": living_ru["id"]}).status_code == 409

    client.post(f"/v1/speech/{living_ru['id']}/approve", headers=AUTH)
    audio = client.post("/v1/tts", headers=AUTH, json={"speech_id": living_ru["id"]})
    assert audio.status_code == 201
    file = client.get(f"/v1/audio/{audio.json()['id']}", headers=AUTH)
    assert file.status_code == 200 and file.content[:4] == b"RIFF"

    export = client.get(f"/v1/projects/{approved_project}/export", headers=AUTH).json()
    assert export["speech"] == [{"room": "LIVING", "lang": "ru", "text": living_ru["text"],
                                 "audio_ids": [audio.json()["id"]]}]


def test_hallucinated_number_is_rejected(client, approved_project, monkeypatch):
    """If the generator invents a number, the API refuses to store the speech."""
    def fake_template(room, lang, tone, facts, key_points):
        return "Гостиная площадью 25 м², ремонт займёт 30 дней."
    monkeypatch.setattr(speech, "template_speech", fake_template)
    r = client.post("/v1/speech", headers=AUTH, json={"project_id": approved_project, "rooms": ["LIVING"]})
    assert r.status_code == 422
    assert {u["number"] for u in r.json()["detail"]["unsupported"]} == {"25", "30"}
    assert client.get(f"/v1/projects/{approved_project}/speech", headers=AUTH).json() == []


def test_language_not_enabled(client, approved_project):
    r = client.post("/v1/speech", headers=AUTH, json={"project_id": approved_project, "languages": ["ky"]})
    assert r.status_code == 422
