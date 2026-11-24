"""Projects, passport and designer key points."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..security import require_api_key

router = APIRouter(prefix="/v1/projects", tags=["projects"], dependencies=[Depends(require_api_key)])


def get_project_or_404(db: Session, project_id: str) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"project '{project_id}' not found")
    return project


@router.post("", response_model=schemas.ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: schemas.ProjectCreate, db: Session = Depends(get_db)):
    if db.get(models.Project, body.id):
        raise HTTPException(status.HTTP_409_CONFLICT, f"project '{body.id}' already exists")
    project = models.Project(**body.model_dump())
    db.add(project)
    db.commit()
    return project


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def read_project(project_id: str, db: Session = Depends(get_db)):
    return get_project_or_404(db, project_id)


@router.put("/{project_id}/passport", response_model=list[schemas.FieldOut])
def upsert_passport(project_id: str, body: schemas.PassportIn, db: Session = Depends(get_db)):
    """Create or update passport fields (sent by the Unreal plugin or edited by the designer).
    Any change resets approval: the designer must approve the passport again."""
    project = get_project_or_404(db, project_id)
    existing = {f.key: f for f in project.fields}
    for item in body.fields:
        field = existing.get(item.key)
        if field is None:
            field = models.PassportField(project_id=project_id, key=item.key)
            db.add(field)
            project.fields.append(field)
        for name, value in item.model_dump().items():
            setattr(field, name, value)
    project.approved = False
    project.approved_at = None
    db.commit()
    db.refresh(project)
    return project.fields


@router.get("/{project_id}/passport", response_model=list[schemas.FieldOut])
def read_passport(project_id: str, db: Session = Depends(get_db)):
    return get_project_or_404(db, project_id).fields


@router.put("/{project_id}/key-points", status_code=status.HTTP_204_NO_CONTENT)
def replace_key_points(project_id: str, body: schemas.KeyPointsIn, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    project.key_points.clear()
    for kp in body.key_points:
        project.key_points.append(models.KeyPoint(project_id=project_id, **kp.model_dump()))
    db.commit()


@router.post("/{project_id}/approve", response_model=schemas.ProjectOut)
def approve_passport(project_id: str, db: Session = Depends(get_db)):
    """Designer approves the passport. Blocked while a required field is empty."""
    project = get_project_or_404(db, project_id)
    missing = [f.key for f in project.fields if f.required and f.value in (None, "")]
    if missing:
        raise HTTPException(status.HTTP_409_CONFLICT, {"message": "required fields are empty", "fields": missing})
    project.approved = True
    project.approved_at = datetime.now(timezone.utc)
    db.commit()
    return project


@router.get("/{project_id}/export")
def export_for_vr(project_id: str, db: Session = Depends(get_db)):
    """Everything the VR app needs offline: approved speech per room and language, with audio ids."""
    get_project_or_404(db, project_id)
    rows = db.scalars(
        select(models.Speech).where(models.Speech.project_id == project_id, models.Speech.status == "approved")
    ).all()
    return {
        "project_id": project_id,
        "speech": [
            {"room": s.room, "lang": s.lang, "text": s.text, "audio_ids": [a.id for a in s.audio]} for s in rows
        ],
    }
