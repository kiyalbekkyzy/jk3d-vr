# JK3DStudio VR

Turns a 3ds Max interior design project into an interactive VR presentation (Unreal Engine 5.8, PICO 4 Ultra)
with an AI guide that speaks only approved facts.

Diploma project, Ala-Too International University, Faculty of Engineering and Informatics.
Author: Kiyalbek kyzy Jasmina. Supervisor: Dr. Andrei Ermakov.

## Repository layout

| Path | Contents |
| --- | --- |
| `backend/` | AI Gateway: FastAPI + PostgreSQL. Passport, guide speech, Fact Guard, text-to-speech |
| `backend/tests/` | Automated tests (pytest): Fact Guard unit tests, API and negative-path tests |
| `unreal/Scripts/` | Python scripts run inside the Unreal editor (link to the AI Gateway, lighting, collision) |
| `unreal/VR_Apartment_Test/` | Unreal project (assets in Git LFS) |
| `docs/` | Architecture, UML diagrams, work logs |
| `docker-compose.yml` | Backend + database for local demo and server |

## Architecture

```
3ds Max (naming standard) --Datasmith--> Unreal editor plugin --passport--> AI Gateway (FastAPI) <--> PostgreSQL
                                               |                               |   \--> LLM API, TTS
                                               v                               v
                                         VR application  <--approved speech + audio
                                         (PICO 4 Ultra via PICO Connect / SteamVR)
```

The guide never speaks unchecked text: the designer approves the passport, speech is generated from the passport
and the designer's key points, **Fact Guard** rejects any number not present in the passport, the designer approves
the speech, and only then is audio produced and exported to the VR application. The show runs offline.

## Run the backend

Requirements: Docker Desktop (Windows) or Docker Engine + Compose.

```bash
cp .env.example .env          # then edit passwords and API_KEY
docker compose up -d --build
curl http://127.0.0.1:8000/health      # {"status":"ok"}
```

Interactive API documentation: <http://127.0.0.1:8000/docs>.

Without Docker (development):

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows; on Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
set DATABASE_URL=sqlite:///./dev.db                 # Linux: export DATABASE_URL=...
set API_KEY=dev-key
uvicorn app.main:app --reload
```

## Configuration (`.env`)

| Variable | Meaning |
| --- | --- |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Database credentials |
| `API_KEY` | Clients send it in the `X-API-Key` header |
| `LLM_PROVIDER` | `template` (offline, deterministic) or `anthropic` (LLM rewrites speech) |
| `ANTHROPIC_API_KEY`, `LLM_MODEL` | Needed only for `anthropic` |
| `TTS_PROVIDER` | `edge` (neural voices; needs internet while generating) or `silent` (stub) |
| `VOICE_RU`, `VOICE_EN` | Voice names |

Secrets are only in `.env`, which is ignored by Git.

## API (v1)

All endpoints except `/health` require `X-API-Key`.

| Method and path | Purpose | Main errors |
| --- | --- | --- |
| `POST /v1/projects` | Create project | 409 exists, 422 invalid |
| `GET /v1/projects/{id}` | Read project | 404 |
| `PUT /v1/projects/{id}/passport` | Create/update passport fields (resets approval) | 404, 422 |
| `GET /v1/projects/{id}/passport` | Read passport | 404 |
| `PUT /v1/projects/{id}/key-points` | Replace designer key points | 404, 422 |
| `POST /v1/projects/{id}/approve` | Approve passport | 409 required field empty |
| `POST /v1/speech` | Generate speech per room and language with Fact Guard | 409 not approved, 422 unsupported numbers |
| `GET /v1/projects/{id}/speech` | List speech | 404 |
| `POST /v1/speech/{id}/approve` | Approve speech | 404 |
| `POST /v1/tts` | Voice an approved speech | 409 not approved, 502 TTS failed |
| `GET /v1/audio/{id}` | Download audio | 404 |
| `GET /v1/projects/{id}/export` | Approved speech + audio ids for the VR app | 404 |
| `GET /health` | Health check (database) | — |

Example of a rejected speech (HTTP 422):

```json
{"detail": {"message": "speech contains numbers that are not in the passport",
            "room": "LIVING", "lang": "ru", "text": "Гостиная площадью 25 м²...",
            "unsupported": [{"number": "25", "unit": "м²", "context": "..."}]}}
```

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q                                   # SQLite
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost/jk3d_test python -m pytest -q   # PostgreSQL
```

20 tests: Fact Guard (supported numbers, rounding, invented area, price and duration, thousands separators),
API key, validation, 404/409/422 paths, approval rules, full flow speech → approval → audio → export,
and a simulated hallucination that must be rejected.

## Unreal editor link

Copy `unreal/Scripts/jk3d_gateway.py` to `<Project>/Content/Python/`, then in the editor Python console:

```python
import jk3d_gateway as g
g.CONFIG.update(url="http://127.0.0.1:8000", api_key="<API_KEY>", project_id="jk3d-001")
g.ensure_project("Pilot apartment", floor=9)
g.send_passport()
g.download_audio()
```

## Deployment (server)

VPS with Ubuntu, 2 vCPU / 4 GB: install Docker, clone the repository, create `.env`, `docker compose up -d`.
Put Nginx with a Let's Encrypt certificate in front of port 8000 (the API is bound to 127.0.0.1 only).
Backup: `docker compose exec db pg_dump -U jk3d jk3d > backup.sql`; audio volume `audio` is copied with the dump.

## Known limitations

- Fact Guard checks numbers written in digits; numbers written as words are not detected (the LLM prompt asks for digits).
- Schema is created on start; Alembic migrations will be added before the release.
- Room areas from the editor script use bounding boxes and must be confirmed by the designer.

## Use of AI tools

Parts of the code and documentation were drafted with Claude (Anthropic) under the author's direction and were
reviewed, tested and adapted by the author. See the thesis, section "Disclosure of AI tool use".
