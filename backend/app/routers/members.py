from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/members", tags=["Members"])


@router.get("", response_model=List[schemas.MemberOut])
def list_members(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(models.Member)
    if status:
        q = q.filter(models.Member.status == status)
    if search:
        term = f"%{search}%"
        q = q.filter(
            models.Member.first.ilike(term) |
            models.Member.last.ilike(term)  |
            models.Member.email.ilike(term) |
            models.Member.ministry.ilike(term)
        )
    return q.order_by(models.Member.last, models.Member.first).all()


@router.post("", response_model=schemas.MemberOut, status_code=201)
def create_member(data: schemas.MemberCreate, db: Session = Depends(get_db)):
    member = models.Member(**data.dict())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get("/{member_id}", response_model=schemas.MemberOut)
def get_member(member_id: str, db: Session = Depends(get_db)):
    m = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    return m


@router.put("/{member_id}", response_model=schemas.MemberOut)
def update_member(member_id: str, data: schemas.MemberUpdate, db: Session = Depends(get_db)):
    m = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return m


@router.delete("/{member_id}", status_code=204)
def delete_member(member_id: str, db: Session = Depends(get_db)):
    m = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(m)
    db.commit()
