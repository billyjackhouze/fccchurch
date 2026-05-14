"""
Organizational hierarchy endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.routers.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/hierarchy", tags=["Hierarchy"])


def build_tree(nodes: list, parent_id: Optional[str] = None) -> List[schemas.OrgNodeOut]:
    """Recursively build a tree from a flat list of OrgNode objects."""
    result = []
    for n in nodes:
        if n.parent_id == parent_id:
            out = schemas.OrgNodeOut(
                id=n.id,
                title=n.title,
                member_id=n.member_id,
                parent_id=n.parent_id,
                sort_order=n.sort_order,
                notes=n.notes,
                created_at=n.created_at,
                member_name=f"{n.member.first} {n.member.last}" if n.member else None,
                member_photo=n.member.photo if n.member else None,
                children=build_tree(nodes, parent_id=n.id),
            )
            result.append(out)
    result.sort(key=lambda x: (x.sort_order or 0, x.title))
    return result


def load_nodes(db: Session):
    from sqlalchemy.orm import joinedload
    return db.query(models.OrgNode).options(
        joinedload(models.OrgNode.member)
    ).all()


# ── Get full tree ─────────────────────────────────────────────────────────────

@router.get("", response_model=List[schemas.OrgNodeOut])
def get_tree(db: Session = Depends(get_db),
             _: models.User = Depends(get_current_user)):
    nodes = load_nodes(db)
    return build_tree(nodes)


# ── Get flat list ─────────────────────────────────────────────────────────────

@router.get("/flat", response_model=List[schemas.OrgNodeOut])
def get_flat(db: Session = Depends(get_db),
             _: models.User = Depends(get_current_user)):
    nodes = load_nodes(db)
    result = []
    for n in nodes:
        result.append(schemas.OrgNodeOut(
            id=n.id,
            title=n.title,
            member_id=n.member_id,
            parent_id=n.parent_id,
            sort_order=n.sort_order,
            notes=n.notes,
            created_at=n.created_at,
            member_name=f"{n.member.first} {n.member.last}" if n.member else None,
            member_photo=n.member.photo if n.member else None,
            children=[],
        ))
    return result


# ── Create node (admin) ───────────────────────────────────────────────────────

@router.post("", response_model=schemas.OrgNodeOut, status_code=201)
def create_node(data: schemas.OrgNodeCreate,
                db: Session = Depends(get_db),
                _: models.User = Depends(require_admin)):
    node = models.OrgNode(**data.dict())
    db.add(node)
    db.commit()
    db.refresh(node)
    # reload with member
    nodes = load_nodes(db)
    flat = {n.id: n for n in nodes}
    n = flat[node.id]
    return schemas.OrgNodeOut(
        id=n.id,
        title=n.title,
        member_id=n.member_id,
        parent_id=n.parent_id,
        sort_order=n.sort_order,
        notes=n.notes,
        created_at=n.created_at,
        member_name=f"{n.member.first} {n.member.last}" if n.member else None,
        member_photo=n.member.photo if n.member else None,
        children=[],
    )


# ── Update node (admin) ───────────────────────────────────────────────────────

@router.put("/{node_id}", response_model=schemas.OrgNodeOut)
def update_node(node_id: str, data: schemas.OrgNodeUpdate,
                db: Session = Depends(get_db),
                _: models.User = Depends(require_admin)):
    node = db.query(models.OrgNode).filter(models.OrgNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(node, k, v)
    db.commit()
    nodes = load_nodes(db)
    flat = {n.id: n for n in nodes}
    n = flat[node.id]
    return schemas.OrgNodeOut(
        id=n.id,
        title=n.title,
        member_id=n.member_id,
        parent_id=n.parent_id,
        sort_order=n.sort_order,
        notes=n.notes,
        created_at=n.created_at,
        member_name=f"{n.member.first} {n.member.last}" if n.member else None,
        member_photo=n.member.photo if n.member else None,
        children=[],
    )


# ── Delete node (admin) ───────────────────────────────────────────────────────

@router.delete("/{node_id}", status_code=204)
def delete_node(node_id: str,
                db: Session = Depends(get_db),
                _: models.User = Depends(require_admin)):
    node = db.query(models.OrgNode).filter(models.OrgNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    # Re-parent children to deleted node's parent
    children = db.query(models.OrgNode).filter(models.OrgNode.parent_id == node_id).all()
    for child in children:
        child.parent_id = node.parent_id
    db.delete(node)
    db.commit()
