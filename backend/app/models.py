"""Database tables: project, passport fields, designer key points, speech, audio."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "project"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "jk3d-001"
    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str] = mapped_column(String(100), default="JK3DStudio")
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    north_offset: Mapped[float | None] = mapped_column(Float, nullable=True)
    languages: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["ru", "en"])
    concept: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"ru": "...", "en": "..."}
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    fields: Mapped[list["PassportField"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    key_points: Mapped[list["KeyPoint"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    speeches: Mapped[list["Speech"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class PassportField(Base):
    """One fact about the project. Only approved passport facts may appear in the guide's speech."""

    __tablename__ = "passport_field"
    __table_args__ = (UniqueConstraint("project_id", "key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(100))  # e.g. "living.area_m2"
    room: Mapped[str | None] = mapped_column(String(64), nullable=True)  # e.g. "LIVING"
    label: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"ru": "Площадь гостиной", "en": "..."}
    value: Mapped[str | None] = mapped_column(String(300), nullable=True)  # stored as text, numbers parsed
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)  # m2, m, cm, K, ...
    source: Mapped[str] = mapped_column(String(16), default="auto")  # auto | designer
    status: Mapped[str] = mapped_column(String(16), default="check")  # ok | check | edited
    required: Mapped[bool] = mapped_column(Boolean, default=False)

    project: Mapped[Project] = relationship(back_populates="fields")


class KeyPoint(Base):
    """Short note written by the designer, e.g. 'kitchen joined with living room at client request'."""

    __tablename__ = "key_point"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    room: Mapped[str] = mapped_column(String(64))
    lang: Mapped[str] = mapped_column(String(8), default="ru")
    text: Mapped[str] = mapped_column(Text)
    order: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped[Project] = relationship(back_populates="key_points")


class Speech(Base):
    __tablename__ = "speech"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    room: Mapped[str] = mapped_column(String(64))
    lang: Mapped[str] = mapped_column(String(8))
    text: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | approved
    fact_check: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped[Project] = relationship(back_populates="speeches")
    audio: Mapped[list["Audio"]] = relationship(back_populates="speech", cascade="all, delete-orphan")


class Audio(Base):
    __tablename__ = "audio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    speech_id: Mapped[int] = mapped_column(ForeignKey("speech.id", ondelete="CASCADE"), index=True)
    voice: Mapped[str] = mapped_column(String(64))
    file_path: Mapped[str] = mapped_column(String(400))
    mime: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    speech: Mapped[Speech] = relationship(back_populates="audio")
