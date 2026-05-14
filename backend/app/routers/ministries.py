"""
Ministry management endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app import models, schemas
from app.routers.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/ministries", tags=["Ministries"])


def enrich_ministry(m: models.Ministry) -> schemas.MinistryOut:
    memberships_out = []
    for ms in m.memberships:
        if ms.member:
            memberships_out.append(schemas.MinistryMembershipOut(
                id=ms.id,
                member_id=ms.member_id,
                member_name=f"{ms.member.first} {ms.member.last}",
                member_photo=ms.member.photo,
                role=ms.role,
                joined_date=ms.joined_date,
            ))
    return schemas.MinistryOut(
        id=m.id,
        name=m.name,
        description=m.description,
        leader_id=m.leader_id,
        leader_name=f"{m.leader.first} {m.leader.last}" if m.leader else None,
        color=m.color,
        member_count=len(memberships_out),
        memberships=memberships_out,
        created_at=m.created_at,
    )


def q_ministries(db):
    return db.query(models.Ministry).options(
        joinedload(models.Ministry.memberships).joinedload(models.MinistryMembership.member),
        joinedload(models.Ministry.leader),
    )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[schemas.MinistryOut])
def list_ministries(db: Session = Depends(get_db),
                    _: models.User = Depends(get_current_user)):
    return [enrich_ministry(m) for m in
            q_ministries(db).order_by(models.Ministry.name).all()]


# ── Get single ────────────────────────────────────────────────────────────────

@router.get("/{ministry_id}", response_model=schemas.MinistryOut)
def get_ministry(ministry_id: str, db: Session = Depends(get_db),
                 _: models.User = Depends(get_current_user)):
    m = q_ministries(db).filter(models.Ministry.id == ministry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Ministry not found")
    return enrich_ministry(m)


# ── Create (admin) ────────────────────────────────────────────────────────────

@router.post("", response_model=schemas.MinistryOut, status_code=201)
def create_ministry(data: schemas.MinistryCreate, db: Session = Depends(get_db),
                    _: models.User = Depends(require_admin)):
    exists = db.query(models.Ministry).filter(models.Ministry.name == data.name).first()
    if exists:
        raise HTTPException(status_code=400, detail="A ministry with that name already exists")
    ministry = models.Ministry(**data.dict())
    db.add(ministry)
    db.commit()
    db.refresh(ministry)
    return enrich_ministry(q_ministries(db).filter(models.Ministry.id == ministry.id).first())


# ── Update (admin) ────────────────────────────────────────────────────────────

@router.put("/{ministry_id}", response_model=schemas.MinistryOut)
def update_ministry(ministry_id: str, data: schemas.MinistryUpdate,
                    db: Session = Depends(get_db),
                    _: models.User = Depends(require_admin)):
    m = db.query(models.Ministry).filter(models.Ministry.id == ministry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Ministry not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    return enrich_ministry(q_ministries(db).filter(models.Ministry.id == ministry_id).first())


# ── Delete (admin) ────────────────────────────────────────────────────────────

@router.delete("/{ministry_id}", status_code=204)
def delete_ministry(ministry_id: str, db: Session = Depends(get_db),
                    _: models.User = Depends(require_admin)):
    m = db.query(models.Ministry).filter(models.Ministry.id == ministry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Ministry not found")
    db.delete(m)
    db.commit()


# ── Add member ────────────────────────────────────────────────────────────────

@router.post("/{ministry_id}/members", response_model=schemas.MinistryMembershipOut,
             status_code=201)
def add_member(ministry_id: str, data: schemas.MinistryMembershipCreate,
               db: Session = Depends(get_db),
               _: models.User = Depends(require_admin)):
    m = db.query(models.Ministry).filter(models.Ministry.id == ministry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Ministry not found")
    member = db.query(models.Member).filter(models.Member.id == data.member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    already = db.query(models.MinistryMembership).filter(
        models.MinistryMembership.ministry_id == ministry_id,
        models.MinistryMembership.member_id == data.member_id,
    ).first()
    if already:
        raise HTTPException(status_code=400, detail="Member is already in this ministry")
    ms = models.MinistryMembership(
        ministry_id=ministry_id,
        member_id=data.member_id,
        role=data.role or "Member",
        joined_date=data.joined_date,
    )
    db.add(ms)
    # Also update member.ministry text field for display everywhere else
    member.ministry = m.name
    db.commit()
    db.refresh(ms)
    return schemas.MinistryMembershipOut(
        id=ms.id,
        member_id=ms.member_id,
        member_name=f"{member.first} {member.last}",
        member_photo=member.photo,
        role=ms.role,
        joined_date=ms.joined_date,
    )


# ── Update member role ────────────────────────────────────────────────────────

@router.put("/{ministry_id}/members/{membership_id}",
            response_model=schemas.MinistryMembershipOut)
def update_member_role(ministry_id: str, membership_id: str,
                       data: schemas.MinistryMembershipCreate,
                       db: Session = Depends(get_db),
                       _: models.User = Depends(require_admin)):
    ms = db.query(models.MinistryMembership).filter(
        models.MinistryMembership.id == membership_id,
        models.MinistryMembership.ministry_id == ministry_id,
    ).first()
    if not ms:
        raise HTTPException(status_code=404, detail="Membership not found")
    if data.role:
        ms.role = data.role
    if data.joined_date:
        ms.joined_date = data.joined_date
    db.commit()
    member = ms.member
    return schemas.MinistryMembershipOut(
        id=ms.id,
        member_id=ms.member_id,
        member_name=f"{member.first} {member.last}",
        member_photo=member.photo,
        role=ms.role,
        joined_date=ms.joined_date,
    )


# ── Remove member ─────────────────────────────────────────────────────────────

@router.delete("/{ministry_id}/members/{membership_id}", status_code=204)
def remove_member(ministry_id: str, membership_id: str,
                  db: Session = Depends(get_db),
                  _: models.User = Depends(require_admin)):
    ms = db.query(models.MinistryMembership).filter(
        models.MinistryMembership.id == membership_id,
        models.MinistryMembership.ministry_id == ministry_id,
    ).first()
    if not ms:
        raise HTTPException(status_code=404, detail="Membership not found")
    db.delete(ms)
    db.commit()
