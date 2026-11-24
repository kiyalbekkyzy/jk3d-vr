"""Guide speech, Fact Guard results, voice audio."""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, speech, tts
from ..config import get_settings
from ..db import get_db
from ..security import require_api_key
from .projects import get_project_or_404

log = logging.getLogger("jk3d.speech")
router = APIRouter(prefix="/v1", tags=["speech"], dependencies=[Depends(require_api_key)])


def passport_values(project: models.Project) -> list:
    return [f.value for f in project.fields] + [project.floor]


@router.post("/speech", response_model=list[schemas.SpeechOut], status_code=status.HTTP_201_CREATED)
def generate_speech(body: schemas.SpeechRequest, db: Session = Depends(get_db)):
    project = get_project_or_404(db, body.project_id)
    if not project.approved:
        raise HTTPException(status.HTTP_409_CONFLICT, "passport is not approved")

    langs = body.languages or project.languages
    unknown = [lang for lang in langs if lang not in project.languages]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"languages not enabled for project: {unknown}")

    rooms = body.rooms or sorted({kp.room for kp in project.key_points} | {f.room for f in project.fields if f.room})
    values = passport_values(project)
    settings = get_settings()
    created = []
    for room in rooms:
        facts = [speech.Fact(f.key, f.room, f.label, f.value, f.unit) for f in project.fields if f.room == room]
        for lang in langs:
            notes = [kp.text for kp in sorted(project.key_points, key=lambda k: k.order)
                     if kp.room == room and (kp.lang == lang or settings.llm_provider == "anthropic")]
            try:
                result = speech.generate(settings, room, lang, body.tone, facts, notes, values)
            except speech.FactCheckFailed as exc:
                log.warning("fact check failed for %s/%s/%s", project.id, room, lang)
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {
                    "message": "speech contains numbers that are not in the passport",
                    "room": room, "lang": lang, "text": exc.text,
                    "unsupported": [i.__dict__ for i in exc.issues],
                })
            row = models.Speech(project_id=project.id, room=room, lang=lang, text=result.text,
                                provider=result.provider, fact_check={"passed": True, "unsupported": []})
            db.add(row)
            created.append(row)
    db.commit()
    return created


@router.get("/projects/{project_id}/speech", response_model=list[schemas.SpeechOut])
def list_speech(project_id: str, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    return db.scalars(select(models.Speech).where(models.Speech.project_id == project_id)).all()


@router.post("/speech/{speech_id}/approve", response_model=schemas.SpeechOut)
def approve_speech(speech_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Speech, speech_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "speech not found")
    row.status = "approved"
    db.commit()
    return row


@router.post("/tts", response_model=schemas.AudioOut, status_code=status.HTTP_201_CREATED)
async def make_audio(body: schemas.TTSRequest, db: Session = Depends(get_db)):
    row = db.get(models.Speech, body.speech_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "speech not found")
    if row.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "only approved speech can be voiced")
    settings = get_settings()
    try:
        path, voice, mime = await tts.synthesize(settings, row.text, row.lang, Path(settings.audio_dir),
                                                 f"{row.project_id}_{row.room}_{row.lang}_{row.id}")
    except tts.TTSError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    audio = models.Audio(speech_id=row.id, voice=voice, file_path=str(path), mime=mime)
    db.add(audio)
    db.commit()
    return audio


@router.get("/audio/{audio_id}")
def download_audio(audio_id: int, db: Session = Depends(get_db)):
    audio = db.get(models.Audio, audio_id)
    if audio is None or not Path(audio.file_path).exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "audio not found")
    return FileResponse(audio.file_path, media_type=audio.mime, filename=Path(audio.file_path).name)
