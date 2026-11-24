"""Application settings, read from environment variables (see .env.example)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database: PostgreSQL in Docker, SQLite is allowed for local tests.
    database_url: str = "postgresql+psycopg://jk3d:jk3d@db:5432/jk3d"

    # Clients (Unreal plugin, VR app) send this key in the X-API-Key header.
    api_key: str = "change-me"

    # Speech generation: "template" works offline, "anthropic" calls the LLM API.
    llm_provider: str = "template"
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-5-5"

    # Voice: "edge" (neural voices, needs internet once), "silent" (tests / offline stub).
    tts_provider: str = "edge"
    voice_ru: str = "ru-RU-SvetlanaNeural"
    voice_en: str = "en-US-JennyNeural"

    audio_dir: str = "/data/audio"


@lru_cache
def get_settings() -> Settings:
    return Settings()
