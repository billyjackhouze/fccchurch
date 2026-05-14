from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/members", tags=["Members"])


def enrich_member(m: models.Member) -> schemas.MemberOut:
    """Convert ORM member to schema, including family relationships."""
    out = schemas.MemberOut.from_orm(m)
    family = []
    for r in m.relationships_from:
        if r.related:
            family.append(schemas.MemberRelationshipOut(
                id=r.id, related_id=r.related_id,
                related_name=f"{r.related.first} {r.related.last}",
                relation=r.relation
            ))
    out.family = family
    return out


def q_members(db):
    return db.query(models.Member).options(
        joinedload(models.Member.relationships_from).joinedload(models.MemberRelationship.related)
    )


@router.get("", response_model=List[schemas.MemberOut])
def list_members(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    q = q_members(db)
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
    return [enrich_member(m) for m in q.order_by(models.Member.last, models.Member.first).all()]


@router.post("", response_model=schemas.MemberOut, status_code=201)
def create_member(data: schemas.MemberCreate, db: Session = Depends(get_db)):
    member = models.Member(**data.dict())
    db.add(member)
    db.commit()
    db.refresh(member)
    return enrich_member(member)


@router.get("/{member_id}", response_model=schemas.MemberOut)
def get_member(member_id: str, db: Session = Depends(get_db)):
    m = q_members(db).filter(models.Member.id == member_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    return enrich_member(m)


@router.put("/{member_id}", response_model=schemas.MemberOut)
def update_member(member_id: str, data: schemas.MemberUpdate, db: Session = Depends(get_db)):
    m = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    return enrich_member(q_members(db).filter(models.Member.id == member_id).first())


@router.delete("/{member_id}", status_code=204)
def delete_member(member_id: str, db: Session = Depends(get_db)):
    m = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(m)
    db.commit()


# ── Family Relationships ──────────────────────────────────────────────────────

@router.post("/{member_id}/family", response_model=schemas.MemberRelationshipOut, status_code=201)
def add_family_member(member_id: str, data: schemas.MemberRelationshipCreate, db: Session = Depends(get_db)):
    """Link two members as family. Creates both directions automatically."""
    if not db.query(models.Member).filter(models.Member.id == member_id).first():
        raise HTTPException(status_code=404, detail="Member not found")
    if not db.query(models.Member).filter(models.Member.id == data.related_id).first():
        raise HTTPException(status_code=404, detail="Related member not found")

    # Reverse relation map
    reverse = {
        'Partner': 'Partner', 'Child': 'Parent', 'Parent': 'Child',
        'Sibling': 'Sibling', 'Guardian': 'Ward', 'Ward': 'Guardian', 'Other': 'Other'
    }
    rel = models.MemberRelationship(member_id=member_id, related_id=data.related_id, relation=data.relation)
    rev = models.MemberRelationship(member_id=data.related_id, related_id=member_id, relation=reverse.get(data.relation, 'Other'))
    db.add(rel); db.add(rev)
    db.commit(); db.refresh(rel)
    related = db.query(models.Member).filter(models.Member.id == data.related_id).first()
    return schemas.MemberRelationshipOut(
        id=rel.id, related_id=rel.related_id,
        related_name=f"{related.first} {related.last}",
        relation=rel.relation
    )


@router.delete("/{member_id}/family/{relation_id}", status_code=204)
def remove_family_member(member_id: str, relation_id: str, db: Session = Depends(get_db)):
    """Remove a family link (removes both directions)."""
    rel = db.query(models.MemberRelationship).filter(models.MemberRelationship.id == relation_id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
    # Remove the reverse link too
    reverse = db.query(models.MemberRelationship).filter(
        models.MemberRelationship.member_id == rel.related_id,
        models.MemberRelationship.related_id == rel.member_id
    ).first()
    db.delete(rel)
    if reverse:
        db.delete(reverse)
    db.commit()
