"""JK3DStudio VR — AI Gateway.

Stores the project passport, generates the guide's speech, checks it with Fact Guard
and produces voice audio for the VR application. API docs: /docs
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from sqlalchemy import text

from . import models  # noqa: F401  (registers tables)
from .db import Base, engine
from .routers import projects, speech

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # simple schema init; Alembic migrations planned for the release
    yield


app = FastAPI(title="JK3DStudio VR — AI Gateway", version="0.1.0", lifespan=lifespan)
app.include_router(projects.router)
app.include_router(speech.router)


@app.get("/health", tags=["health"])
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
