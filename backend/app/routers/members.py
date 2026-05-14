from typing import List, Optional
import os, shutil
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/members", tags=["Members"])

RELATION_REVERSE = {
    'Partner':    'Partner',
    'Child':      'Parent',
    'Parent':     'Child',
    'Sibling':    'Sibling',
    'Guardian':   'Ward',
    'Ward':       'Guardian',
    'Grandparent':'Grandchild',
    'Grandchild': 'Grandparent',
    'Aunt/Uncle': 'Niece/Nephew',
    'Niece/Nephew':'Aunt/Uncle',
    'Other':      'Other',
}


def enrich_member(m: models.Member) -> schemas.MemberOut:
    out = schemas.MemberOut.from_orm(m)
    family = []
    for r in m.relationships_from:
        if r.related:
            family.append(schemas.MemberRelationshipOut(
                id=r.id,
                related_id=r.related_id,
                related_name=f"{r.related.first} {r.related.last}",
                relation=r.relation,
                related_photo=r.related.photo,
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


# ── Photo Upload ──────────────────────────────────────────────────────────────

@router.post("/{member_id}/photo")
async def upload_photo(member_id: str, file: UploadFile = File(...),
                       db: Session = Depends(get_db)):
    m = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    ext = (file.filename or "photo.jpg").rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
        ext = "jpg"
    filename = f"{member_id}.{ext}"

    photos_dir = os.path.join(os.path.dirname(__file__), "..", "..", "static", "photos")
    os.makedirs(photos_dir, exist_ok=True)

    # Remove old photo if different extension
    for old_ext in ("jpg", "jpeg", "png", "gif", "webp"):
        old_path = os.path.join(photos_dir, f"{member_id}.{old_ext}")
        if os.path.exists(old_path) and old_ext != ext:
            os.remove(old_path)

    file_path = os.path.join(photos_dir, filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    m.photo = filename
    db.commit()
    return {"photo": filename, "url": f"/static/photos/{filename}"}


# ── Family Relationships ──────────────────────────────────────────────────────

@router.post("/{member_id}/family", response_model=schemas.MemberRelationshipOut, status_code=201)
def add_family_member(member_id: str, data: schemas.MemberRelationshipCreate,
                      db: Session = Depends(get_db)):
    if not db.query(models.Member).filter(models.Member.id == member_id).first():
        raise HTTPException(status_code=404, detail="Member not found")
    related = db.query(models.Member).filter(models.Member.id == data.related_id).first()
    if not related:
        raise HTTPException(status_code=404, detail="Related member not found")

    rel = models.MemberRelationship(member_id=member_id, related_id=data.related_id, relation=data.relation)
    rev = models.MemberRelationship(member_id=data.related_id, related_id=member_id,
                                    relation=RELATION_REVERSE.get(data.relation, "Other"))
    db.add(rel); db.add(rev)
    db.commit(); db.refresh(rel)

    return schemas.MemberRelationshipOut(
        id=rel.id, related_id=rel.related_id,
        related_name=f"{related.first} {related.last}",
        relation=rel.relation,
        related_photo=related.photo,
    )


# ── Member Activity (giving + pledges summary) ───────────────────────────────

@router.get("/{member_id}/activity")
def get_member_activity(member_id: str, db: Session = Depends(get_db)):
    from datetime import date as dt_date
    m = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    now_year = dt_date.today().year
    giving_records = db.query(models.GivingRecord).filter(
        models.GivingRecord.member_id == member_id
    ).order_by(models.GivingRecord.date.desc()).all()
    pledges = db.query(models.Pledge).filter(
        models.Pledge.member_id == member_id
    ).all()
    giving_total      = float(sum(g.amount for g in giving_records))
    giving_this_year  = float(sum(g.amount for g in giving_records if g.date.year == now_year))
    return {
        "giving": [{"id":g.id,"date":str(g.date),"amount":float(g.amount),"type":g.type,"fund":g.fund,"notes":g.notes} for g in giving_records],
        "pledges": [{"id":p.id,"campaign":p.campaign,"pledged_amount":float(p.pledged_amount),"paid_amount":float(p.paid_amount),"pledge_date":str(p.pledge_date) if p.pledge_date else None,"end_date":str(p.end_date) if p.end_date else None,"frequency":p.frequency,"status":p.status} for p in pledges],
        "giving_total": giving_total,
        "giving_this_year": giving_this_year,
    }


@router.delete("/{member_id}/family/{relation_id}", status_code=204)
def remove_family_member(member_id: str, relation_id: str, db: Session = Depends(get_db)):
    rel = db.query(models.MemberRelationship).filter(
        models.MemberRelationship.id == relation_id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
    reverse = db.query(models.MemberRelationship).filter(
        models.MemberRelationship.member_id == rel.related_id,
        models.MemberRelationship.related_id == rel.member_id
    ).first()
    db.delete(rel)
    if reverse:
        db.delete(reverse)
    db.commit()
