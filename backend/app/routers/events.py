from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/events", tags=["Events"])


@router.get("", response_model=List[schemas.EventOut])
def list_events(
    from_date: Optional[date] = Query(None),
    to_date:   Optional[date] = Query(None),
    type:      Optional[str]  = Query(None),
    room_id:   Optional[str]  = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(models.Event).options(joinedload(models.Event.room))
    if from_date:
        q = q.filter(models.Event.date >= from_date)
    if to_date:
        q = q.filter(models.Event.date <= to_date)
    if type:
        q = q.filter(models.Event.type == type)
    if room_id:
        q = q.filter(models.Event.room_id == room_id)
    events = q.order_by(models.Event.date, models.Event.start_time).all()
    result = []
    for e in events:
        out = schemas.EventOut.from_orm(e)
        out.room_name = e.room.name if e.room else None
        result.append(out)
    return result


@router.post("", response_model=schemas.EventOut, status_code=201)
def create_event(data: schemas.EventCreate, db: Session = Depends(get_db)):
    event = models.Event(**data.dict())
    db.add(event)
    db.commit()
    db.refresh(event)
    out = schemas.EventOut.from_orm(event)
    if event.room:
        out.room_name = event.room.name
    return out


@router.get("/{event_id}", response_model=schemas.EventOut)
def get_event(event_id: str, db: Session = Depends(get_db)):
    e = db.query(models.Event).options(joinedload(models.Event.room)).filter(models.Event.id == event_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    out = schemas.EventOut.from_orm(e)
    out.room_name = e.room.name if e.room else None
    return out


@router.put("/{event_id}", response_model=schemas.EventOut)
def update_event(event_id: str, data: schemas.EventUpdate, db: Session = Depends(get_db)):
    e = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(e, k, v)
    db.commit()
    db.refresh(e)
    return e


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: str, db: Session = Depends(get_db)):
    e = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(e)
    db.commit()
