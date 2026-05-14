"""
Sermon archive endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app import models, schemas
from app.routers.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/sermons", tags=["Sermons"])


def enrich_sermon(s: models.Sermon) -> schemas.SermonOut:
    return schemas.SermonOut(
        id=s.id,
        title=s.title,
        date=s.date,
        series_name=s.series_name,
        scripture=s.scripture,
        preacher_id=s.preacher_id,
        plan_id=s.plan_id,
        sermon_notes=s.sermon_notes,
        tags=s.tags,
        preacher_name=f"{s.preacher.first} {s.preacher.last}" if s.preacher else None,
        plan_title=s.plan.title if s.plan else None,
        created_at=s.created_at,
    )


def q_sermons(db):
    return db.query(models.Sermon).options(
        joinedload(models.Sermon.preacher),
        joinedload(models.Sermon.plan),
    )


@router.get("", response_model=List[schemas.SermonOut])
def list_sermons(
    search: Optional[str] = Query(None),
    series: Optional[str] = Query(None),
    preacher_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = q_sermons(db)
    if search:
        like = f"%{search}%"
        q = q.filter(
            (models.Sermon.title.ilike(like)) |
            (models.Sermon.scripture.ilike(like)) |
            (models.Sermon.series_name.ilike(like)) |
            (models.Sermon.tags.ilike(like))
        )
    if series:
        q = q.filter(models.Sermon.series_name == series)
    if preacher_id:
        q = q.filter(models.Sermon.preacher_id == preacher_id)
    sermons = q.order_by(models.Sermon.date.desc()).all()
    return [enrich_sermon(s) for s in sermons]


@router.get("/{sermon_id}", response_model=schemas.SermonOut)
def get_sermon(sermon_id: str, db: Session = Depends(get_db),
               _: models.User = Depends(get_current_user)):
    s = q_sermons(db).filter(models.Sermon.id == sermon_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sermon not found")
    return enrich_sermon(s)


@router.post("", response_model=schemas.SermonOut, status_code=201)
def create_sermon(data: schemas.SermonCreate, db: Session = Depends(get_db),
                  _: models.User = Depends(require_admin)):
    s = models.Sermon(**data.dict())
    db.add(s)
    db.commit()
    db.refresh(s)
    return enrich_sermon(q_sermons(db).filter(models.Sermon.id == s.id).first())


@router.put("/{sermon_id}", response_model=schemas.SermonOut)
def update_sermon(sermon_id: str, data: schemas.SermonUpdate,
                  db: Session = Depends(get_db),
                  _: models.User = Depends(require_admin)):
    s = db.query(models.Sermon).filter(models.Sermon.id == sermon_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sermon not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    return enrich_sermon(q_sermons(db).filter(models.Sermon.id == sermon_id).first())


@router.delete("/{sermon_id}", status_code=204)
def delete_sermon(sermon_id: str, db: Session = Depends(get_db),
                  _: models.User = Depends(require_admin)):
    s = db.query(models.Sermon).filter(models.Sermon.id == sermon_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sermon not found")
    db.delete(s)
    db.commit()
