from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/pledges", tags=["Pledges"])


@router.get("", response_model=List[schemas.PledgeOut])
def list_pledges(
    status:    Optional[str] = Query(None),
    campaign:  Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(models.Pledge).options(joinedload(models.Pledge.member))
    if status:
        q = q.filter(models.Pledge.status == status)
    if campaign:
        q = q.filter(models.Pledge.campaign.ilike(f"%{campaign}%"))
    pledges = q.order_by(models.Pledge.created_at.desc()).all()
    result = []
    for p in pledges:
        out = schemas.PledgeOut.from_orm(p)
        out.member_name = f"{p.member.first} {p.member.last}" if p.member else "Anonymous"
        out.balance = p.pledged_amount - p.paid_amount
        result.append(out)
    return result


@router.post("", response_model=schemas.PledgeOut, status_code=201)
def create_pledge(data: schemas.PledgeCreate, db: Session = Depends(get_db)):
    pledge = models.Pledge(**data.dict())
    db.add(pledge)
    db.commit()
    db.refresh(pledge)
    out = schemas.PledgeOut.from_orm(pledge)
    out.balance = pledge.pledged_amount - pledge.paid_amount
    return out


@router.put("/{pledge_id}", response_model=schemas.PledgeOut)
def update_pledge(pledge_id: str, data: schemas.PledgeUpdate, db: Session = Depends(get_db)):
    """Update payment progress or status of a pledge."""
    p = db.query(models.Pledge).filter(models.Pledge.id == pledge_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Pledge not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(p, k, v)
    # Auto-mark fulfilled if fully paid
    if p.paid_amount >= p.pledged_amount:
        p.status = "Fulfilled"
    db.commit()
    db.refresh(p)
    out = schemas.PledgeOut.from_orm(p)
    out.balance = p.pledged_amount - p.paid_amount
    if p.member:
        out.member_name = f"{p.member.first} {p.member.last}"
    return out


@router.delete("/{pledge_id}", status_code=204)
def delete_pledge(pledge_id: str, db: Session = Depends(get_db)):
    p = db.query(models.Pledge).filter(models.Pledge.id == pledge_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Pledge not found")
    db.delete(p)
    db.commit()
