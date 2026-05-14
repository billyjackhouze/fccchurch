from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/rooms", tags=["Rooms"])


@router.get("", response_model=List[schemas.RoomOut])
def list_rooms(db: Session = Depends(get_db)):
    return db.query(models.Room).order_by(models.Room.name).all()


@router.post("", response_model=schemas.RoomOut, status_code=201)
def create_room(data: schemas.RoomCreate, db: Session = Depends(get_db)):
    room = models.Room(**data.dict())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get("/{room_id}", response_model=schemas.RoomOut)
def get_room(room_id: str, db: Session = Depends(get_db)):
    r = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Room not found")
    return r


@router.put("/{room_id}", response_model=schemas.RoomOut)
def update_room(room_id: str, data: schemas.RoomUpdate, db: Session = Depends(get_db)):
    r = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Room not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return r


@router.delete("/{room_id}", status_code=204)
def delete_room(room_id: str, db: Session = Depends(get_db)):
    r = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Room not found")
    db.delete(r)
    db.commit()
