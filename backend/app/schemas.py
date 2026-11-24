"""Request and response models (validated by Pydantic, documented in /docs)."""
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

LANG_RE = re.compile(r"^[a-z]{2}$")  # ISO 639-1
ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def _check_langs(v: list[str]) -> list[str]:
    for code in v:
        if not LANG_RE.match(code):
            raise ValueError(f"language must be an ISO 639-1 code, got '{code}'")
    return v


class ProjectCreate(BaseModel):
    id: str = Field(examples=["jk3d-001"])
    name: str = Field(min_length=1, max_length=200)
    brand: str = "JK3DStudio"
    address: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    floor: int | None = Field(default=None, ge=-5, le=200)
    north_offset: float | None = Field(default=None, ge=-360, le=360)
    languages: list[str] = ["ru", "en"]
    concept: dict[str, str] | None = None

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not ID_RE.match(v):
            raise ValueError("id may contain only letters, digits, '-' and '_' (max 64)")
        return v

    _langs = field_validator("languages")(classmethod(lambda cls, v: _check_langs(v)))


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    brand: str
    address: str | None
    floor: int | None
    languages: list[str]
    approved: bool


class FieldIn(BaseModel):
    key: str = Field(min_length=1, max_length=100, examples=["living.area_m2"])
    room: str | None = Field(default=None, examples=["LIVING"])
    label: dict[str, str] | None = None
    value: str | None = None
    unit: str | None = Field(default=None, max_length=16)
    source: str = Field(default="auto", pattern="^(auto|designer)$")
    status: str = Field(default="check", pattern="^(ok|check|edited)$")
    required: bool = False


class FieldOut(FieldIn):
    model_config = ConfigDict(from_attributes=True)


class PassportIn(BaseModel):
    fields: list[FieldIn]


class KeyPointIn(BaseModel):
    room: str = Field(min_length=1, max_length=64)
    lang: str = "ru"
    text: str = Field(min_length=1, max_length=1000)
    order: int = 0


class KeyPointsIn(BaseModel):
    key_points: list[KeyPointIn]


class SpeechRequest(BaseModel):
    project_id: str
    rooms: list[str] | None = None  # None = every room that has key points or facts
    languages: list[str] | None = None  # None = project languages
    tone: str = Field(default="friendly", pattern="^(friendly|business|premium)$")


class FactIssue(BaseModel):
    number: str
    unit: str | None
    context: str


class SpeechOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: str
    room: str
    lang: str
    text: str
    provider: str
    status: str
    fact_check: dict


class TTSRequest(BaseModel):
    speech_id: int


class AudioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    speech_id: int
    voice: str
    mime: str
