"""
Church groups (small groups, bible studies, prayer groups, etc.) endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app import models, schemas
from app.routers.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/groups", tags=["Groups"])


def enrich_group(g: models.Group) -> schemas.GroupOut:
    memberships_out = []
    for ms in g.memberships:
        if ms.member:
            memberships_out.append(schemas.GroupMembershipOut(
                id=ms.id,
                member_id=ms.member_id,
                member_name=f"{ms.member.first} {ms.member.last}",
                member_photo=ms.member.photo,
                role=ms.role,
                joined_date=ms.joined_date,
            ))
    return schemas.GroupOut(
        id=g.id,
        name=g.name,
        group_type=g.group_type,
        leader_id=g.leader_id,
        leader_name=f"{g.leader.first} {g.leader.last}" if g.leader else None,
        meeting_day=g.meeting_day,
        meeting_time=g.meeting_time,
        location=g.location,
        description=g.description,
        is_active=g.is_active,
        color=g.color,
        member_count=len(memberships_out),
        memberships=memberships_out,
        created_at=g.created_at,
    )


def q_groups(db):
    return db.query(models.Group).options(
        joinedload(models.Group.memberships).joinedload(models.GroupMembership.member),
        joinedload(models.Group.leader),
    )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[schemas.GroupOut])
def list_groups(db: Session = Depends(get_db),
                _: models.User = Depends(get_current_user)):
    return [enrich_group(g) for g in
            q_groups(db).order_by(models.Group.name).all()]


# ── Get single ────────────────────────────────────────────────────────────────

@router.get("/{group_id}", response_model=schemas.GroupOut)
def get_group(group_id: str, db: Session = Depends(get_db),
              _: models.User = Depends(get_current_user)):
    g = q_groups(db).filter(models.Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    return enrich_group(g)


# ── Create (admin) ────────────────────────────────────────────────────────────

@router.post("", response_model=schemas.GroupOut, status_code=201)
def create_group(data: schemas.GroupCreate, db: Session = Depends(get_db),
                 _: models.User = Depends(require_admin)):
    exists = db.query(models.Group).filter(models.Group.name == data.name).first()
    if exists:
        raise HTTPException(status_code=400, detail="A group with that name already exists")
    group = models.Group(**data.dict())
    db.add(group)
    db.commit()
    db.refresh(group)
    return enrich_group(q_groups(db).filter(models.Group.id == group.id).first())


# ── Update (admin) ────────────────────────────────────────────────────────────

@router.put("/{group_id}", response_model=schemas.GroupOut)
def update_group(group_id: str, data: schemas.GroupUpdate,
                 db: Session = Depends(get_db),
                 _: models.User = Depends(require_admin)):
    g = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(g, k, v)
    db.commit()
    return enrich_group(q_groups(db).filter(models.Group.id == group_id).first())


# ── Delete (admin) ────────────────────────────────────────────────────────────

@router.delete("/{group_id}", status_code=204)
def delete_group(group_id: str, db: Session = Depends(get_db),
                 _: models.User = Depends(require_admin)):
    g = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    db.delete(g)
    db.commit()


# ── Add member ────────────────────────────────────────────────────────────────

@router.post("/{group_id}/members", response_model=schemas.GroupMembershipOut,
             status_code=201)
def add_member(group_id: str, data: schemas.GroupMembershipCreate,
               db: Session = Depends(get_db),
               _: models.User = Depends(require_admin)):
    g = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    member = db.query(models.Member).filter(models.Member.id == data.member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    already = db.query(models.GroupMembership).filter(
        models.GroupMembership.group_id == group_id,
        models.GroupMembership.member_id == data.member_id,
    ).first()
    if already:
        raise HTTPException(status_code=400, detail="Member is already in this group")
    ms = models.GroupMembership(
        group_id=group_id,
        member_id=data.member_id,
        role=data.role or "Member",
        joined_date=data.joined_date,
    )
    db.add(ms)
    db.commit()
    db.refresh(ms)
    return schemas.GroupMembershipOut(
        id=ms.id,
        member_id=ms.member_id,
        member_name=f"{member.first} {member.last}",
        member_photo=member.photo,
        role=ms.role,
        joined_date=ms.joined_date,
    )


# ── Update member role ────────────────────────────────────────────────────────

@router.put("/{group_id}/members/{membership_id}",
            response_model=schemas.GroupMembershipOut)
def update_member_role(group_id: str, membership_id: str,
                       data: schemas.GroupMembershipCreate,
                       db: Session = Depends(get_db),
                       _: models.User = Depends(require_admin)):
    ms = db.query(models.GroupMembership).filter(
        models.GroupMembership.id == membership_id,
        models.GroupMembership.group_id == group_id,
    ).first()
    if not ms:
        raise HTTPException(status_code=404, detail="Membership not found")
    if data.role:
        ms.role = data.role
    if data.joined_date:
        ms.joined_date = data.joined_date
    db.commit()
    member = ms.member
    return schemas.GroupMembershipOut(
        id=ms.id,
        member_id=ms.member_id,
        member_name=f"{member.first} {member.last}",
        member_photo=member.photo,
        role=ms.role,
        joined_date=ms.joined_date,
    )


# ── Remove member ─────────────────────────────────────────────────────────────

@router.delete("/{group_id}/members/{membership_id}", status_code=204)
def remove_member(group_id: str, membership_id: str,
                  db: Session = Depends(get_db),
                  _: models.User = Depends(require_admin)):
    ms = db.query(models.GroupMembership).filter(
        models.GroupMembership.id == membership_id,
        models.GroupMembership.group_id == group_id,
    ).first()
    if not ms:
        raise HTTPException(status_code=404, detail="Membership not found")
    db.delete(ms)
    db.commit()
