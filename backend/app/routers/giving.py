from typing import List, Optional
from decimal import Decimal
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import extract, func
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/giving", tags=["Giving"])


@router.get("", response_model=List[schemas.GivingOut])
def list_giving(
    year:      Optional[int] = Query(None),
    member_id: Optional[str] = Query(None),
    type:      Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(models.GivingRecord).options(joinedload(models.GivingRecord.member))
    if year:
        q = q.filter(extract('year', models.GivingRecord.date) == year)
    if member_id:
        q = q.filter(models.GivingRecord.member_id == member_id)
    if type:
        q = q.filter(models.GivingRecord.type == type)
    records = q.order_by(models.GivingRecord.date.desc()).all()
    result = []
    for r in records:
        out = schemas.GivingOut.from_orm(r)
        out.member_name = f"{r.member.first} {r.member.last}" if r.member else "Anonymous"
        result.append(out)
    return result


@router.get("/summary")
def giving_summary(year: Optional[int] = Query(None), db: Session = Depends(get_db)):
    """Returns total giving by fund/type for the given year (defaults to current year)."""
    from datetime import datetime
    y = year or datetime.utcnow().year
    rows = (
        db.query(models.GivingRecord.type, func.sum(models.GivingRecord.amount).label("total"))
        .filter(extract('year', models.GivingRecord.date) == y)
        .group_by(models.GivingRecord.type)
        .all()
    )
    return {r.type: float(r.total) for r in rows}


@router.post("", response_model=schemas.GivingOut, status_code=201)
def create_giving(data: schemas.GivingCreate, db: Session = Depends(get_db)):
    record = models.GivingRecord(**data.dict())
    db.add(record)
    db.commit()
    db.refresh(record)
    out = schemas.GivingOut.from_orm(record)
    if record.member:
        out.member_name = f"{record.member.first} {record.member.last}"
    return out


@router.delete("/{giving_id}", status_code=204)
def delete_giving(giving_id: str, db: Session = Depends(get_db)):
    r = db.query(models.GivingRecord).filter(models.GivingRecord.id == giving_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(r)
    db.commit()
