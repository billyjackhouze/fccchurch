"""
User management — admins can create/manage accounts, members can update their own.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth_utils import hash_password
from app.routers.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/users", tags=["Users"])


def _enrich(u: models.User) -> schemas.UserOut:
    name = f"{u.member.first} {u.member.last}" if u.member else None
    return schemas.UserOut(
        id=u.id, email=u.email, role=u.role, is_active=u.is_active,
        member_id=u.member_id, member_name=name, created_at=u.created_at
    )


@router.get("", response_model=List[schemas.UserOut])
def list_users(current_user=Depends(require_admin), db: Session = Depends(get_db)):
    return [_enrich(u) for u in db.query(models.User).all()]


@router.post("", response_model=schemas.UserOut, status_code=201)
def create_user(data: schemas.UserCreate, current_user=Depends(require_admin),
                db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role or "member",
        member_id=data.member_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _enrich(user)


@router.put("/{user_id}", response_model=schemas.UserOut)
def update_user(user_id: str, data: schemas.UserUpdate,
                current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if data.email:
        user.email = data.email
    if data.password:
        user.password_hash = hash_password(data.password)
    if data.role and current_user.role == "admin":
        user.role = data.role
    if data.is_active is not None and current_user.role == "admin":
        user.is_active = data.is_active
    if data.member_id is not None and current_user.role == "admin":
        user.member_id = data.member_id or None
    db.commit()
    db.refresh(user)
    return _enrich(user)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: str, current_user=Depends(require_admin),
                db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
