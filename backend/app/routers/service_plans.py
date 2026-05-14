"""
Service Planning endpoints — plans, order of service items, sermon notes.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app import models, schemas
from app.routers.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/services", tags=["Services"])


def enrich_plan(p: models.ServicePlan) -> schemas.ServicePlanOut:
    items = sorted(p.items, key=lambda x: x.sort_order)
    return schemas.ServicePlanOut(
        id=p.id,
        title=p.title,
        date=p.date,
        service_type=p.service_type,
        status=p.status,
        series_name=p.series_name,
        sermon_title=p.sermon_title,
        sermon_scripture=p.sermon_scripture,
        sermon_notes=p.sermon_notes,
        preacher_id=p.preacher_id,
        preacher_name=f"{p.preacher.first} {p.preacher.last}" if p.preacher else None,
        notes=p.notes,
        items=[schemas.ServiceItemOut(
            id=i.id, plan_id=i.plan_id, item_type=i.item_type,
            title=i.title, duration_minutes=i.duration_minutes,
            notes=i.notes, color=i.color, sort_order=i.sort_order,
            created_at=i.created_at,
        ) for i in items],
        item_count=len(items),
        total_minutes=sum(i.duration_minutes or 0 for i in items),
        created_at=p.created_at,
    )


def q_plans(db):
    return db.query(models.ServicePlan).options(
        joinedload(models.ServicePlan.preacher),
        joinedload(models.ServicePlan.items),
    )


# ── List plans ────────────────────────────────────────────────────────────────

@router.get("", response_model=List[schemas.ServicePlanOut])
def list_plans(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = q_plans(db)
    if status:
        q = q.filter(models.ServicePlan.status == status)
    plans = q.order_by(models.ServicePlan.date.desc()).all()
    return [enrich_plan(p) for p in plans]


# ── Get single plan ───────────────────────────────────────────────────────────

@router.get("/{plan_id}", response_model=schemas.ServicePlanOut)
def get_plan(plan_id: str, db: Session = Depends(get_db),
             _: models.User = Depends(get_current_user)):
    p = q_plans(db).filter(models.ServicePlan.id == plan_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Service plan not found")
    return enrich_plan(p)


# ── Create plan (admin) ───────────────────────────────────────────────────────

@router.post("", response_model=schemas.ServicePlanOut, status_code=201)
def create_plan(data: schemas.ServicePlanCreate, db: Session = Depends(get_db),
                _: models.User = Depends(require_admin)):
    plan = models.ServicePlan(**data.dict())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return enrich_plan(q_plans(db).filter(models.ServicePlan.id == plan.id).first())


# ── Update plan (admin) ───────────────────────────────────────────────────────

@router.put("/{plan_id}", response_model=schemas.ServicePlanOut)
def update_plan(plan_id: str, data: schemas.ServicePlanUpdate,
                db: Session = Depends(get_db),
                _: models.User = Depends(require_admin)):
    p = db.query(models.ServicePlan).filter(models.ServicePlan.id == plan_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Service plan not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    return enrich_plan(q_plans(db).filter(models.ServicePlan.id == plan_id).first())


# ── Delete plan (admin) ───────────────────────────────────────────────────────

@router.delete("/{plan_id}", status_code=204)
def delete_plan(plan_id: str, db: Session = Depends(get_db),
                _: models.User = Depends(require_admin)):
    p = db.query(models.ServicePlan).filter(models.ServicePlan.id == plan_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Service plan not found")
    db.delete(p)
    db.commit()


# ── Move plan to status (admin) ───────────────────────────────────────────────

@router.patch("/{plan_id}/status", response_model=schemas.ServicePlanOut)
def update_status(plan_id: str, body: dict, db: Session = Depends(get_db),
                  _: models.User = Depends(require_admin)):
    valid = {"draft", "planning", "ready", "complete"}
    new_status = body.get("status", "")
    if new_status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid}")
    p = db.query(models.ServicePlan).filter(models.ServicePlan.id == plan_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Service plan not found")
    p.status = new_status
    db.commit()
    return enrich_plan(q_plans(db).filter(models.ServicePlan.id == plan_id).first())


# ── Add item to plan (admin) ──────────────────────────────────────────────────

@router.post("/{plan_id}/items", response_model=schemas.ServiceItemOut, status_code=201)
def add_item(plan_id: str, data: schemas.ServiceItemCreate,
             db: Session = Depends(get_db),
             _: models.User = Depends(require_admin)):
    p = db.query(models.ServicePlan).filter(models.ServicePlan.id == plan_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Service plan not found")
    # Auto sort_order = max + 1
    existing = db.query(models.ServiceItem).filter(
        models.ServiceItem.plan_id == plan_id).all()
    max_order = max((i.sort_order for i in existing), default=-1)
    item = models.ServiceItem(
        plan_id=plan_id,
        sort_order=data.sort_order if data.sort_order else max_order + 1,
        **{k: v for k, v in data.dict().items() if k != "sort_order"},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return schemas.ServiceItemOut(
        id=item.id, plan_id=item.plan_id, item_type=item.item_type,
        title=item.title, duration_minutes=item.duration_minutes,
        notes=item.notes, color=item.color, sort_order=item.sort_order,
        created_at=item.created_at,
    )


# ── Update item (admin) ───────────────────────────────────────────────────────

@router.put("/{plan_id}/items/{item_id}", response_model=schemas.ServiceItemOut)
def update_item(plan_id: str, item_id: str, data: schemas.ServiceItemUpdate,
                db: Session = Depends(get_db),
                _: models.User = Depends(require_admin)):
    item = db.query(models.ServiceItem).filter(
        models.ServiceItem.id == item_id,
        models.ServiceItem.plan_id == plan_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit()
    return schemas.ServiceItemOut(
        id=item.id, plan_id=item.plan_id, item_type=item.item_type,
        title=item.title, duration_minutes=item.duration_minutes,
        notes=item.notes, color=item.color, sort_order=item.sort_order,
        created_at=item.created_at,
    )


# ── Delete item (admin) ───────────────────────────────────────────────────────

@router.delete("/{plan_id}/items/{item_id}", status_code=204)
def delete_item(plan_id: str, item_id: str, db: Session = Depends(get_db),
                _: models.User = Depends(require_admin)):
    item = db.query(models.ServiceItem).filter(
        models.ServiceItem.id == item_id,
        models.ServiceItem.plan_id == plan_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()


# ── Reorder items (admin) — drag-and-drop saves ───────────────────────────────

@router.patch("/{plan_id}/items/reorder", status_code=204)
def reorder_items(plan_id: str, data: schemas.ServiceItemReorder,
                  db: Session = Depends(get_db),
                  _: models.User = Depends(require_admin)):
    items = db.query(models.ServiceItem).filter(
        models.ServiceItem.plan_id == plan_id).all()
    item_map = {i.id: i for i in items}
    for idx, item_id in enumerate(data.ordered_ids):
        if item_id in item_map:
            item_map[item_id].sort_order = idx
    db.commit()
