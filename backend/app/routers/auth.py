"""
Authentication endpoints — login, password change, forgot/reset password, setup.
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import secrets, smtplib, os
from email.mime.text import MIMEText

from app.database import get_db
from app import models, schemas
from app.auth_utils import hash_password, verify_password, create_token, decode_token

router = APIRouter(prefix="/api/auth", tags=["Auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(models.User).filter(models.User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ── Setup (first-time admin creation) ────────────────────────────────────────

@router.get("/setup-status")
def setup_status(db: Session = Depends(get_db)):
    count = db.query(models.User).count()
    return {"needs_setup": count == 0}


@router.post("/setup", response_model=schemas.TokenOut)
def setup(data: schemas.UserCreate, db: Session = Depends(get_db)):
    """Create first admin account. Only works when no users exist."""
    if db.query(models.User).count() > 0:
        raise HTTPException(status_code=400, detail="Setup already complete")
    user = models.User(
        email=data.email,
        password_hash=hash_password(data.password),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token({"sub": user.id, "role": user.role, "email": user.email})
    return schemas.TokenOut(access_token=token, token_type="bearer", role=user.role,
                            user_id=user.id, member_id=user.member_id)


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=schemas.TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is inactive")
    token = create_token({"sub": user.id, "role": user.role, "email": user.email})
    return schemas.TokenOut(access_token=token, token_type="bearer", role=user.role,
                            user_id=user.id, member_id=user.member_id)


@router.get("/me")
def me(current_user: models.User = Depends(get_current_user)):
    member_name = None
    if current_user.member:
        member_name = f"{current_user.member.first} {current_user.member.last}"
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "member_id": current_user.member_id,
        "member_name": member_name,
    }


# ── Password management ───────────────────────────────────────────────────────

@router.post("/change-password")
def change_password(data: schemas.PasswordChange,
                    current_user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


@router.post("/forgot-password")
def forgot_password(data: schemas.ForgotPassword, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user:
        return {"message": "If that email is registered, a reset link has been sent."}

    token = secrets.token_urlsafe(32)
    user.reset_token  = token
    user.reset_expiry = datetime.utcnow() + timedelta(hours=2)
    db.commit()

    base_url = os.getenv("APP_URL", "https://fcc.bjesoftware.com")
    reset_url = f"{base_url}/?reset={token}"

    smtp_host = os.getenv("SMTP_HOST", "")
    if smtp_host:
        try:
            msg = MIMEText(
                f"Someone requested a password reset for your FCC Church account.\n\n"
                f"Click this link to reset your password:\n{reset_url}\n\n"
                f"This link expires in 2 hours. If you did not request this, ignore this email."
            )
            msg["Subject"] = "FCC Church — Password Reset"
            msg["From"]    = os.getenv("SMTP_FROM", "noreply@fcc.bjesoftware.com")
            msg["To"]      = user.email
            with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "587"))) as s:
                s.starttls()
                s.login(os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASS", ""))
                s.send_message(msg)
        except Exception as ex:
            print(f"Email send failed: {ex}")

    # Return token in response when SMTP not configured (admin can relay it manually)
    return {
        "message": "If that email is registered, a reset link has been sent.",
        "reset_token": token if not smtp_host else None
    }


@router.post("/reset-password")
def reset_password(data: schemas.ResetPassword, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.reset_token == data.token,
        models.User.reset_expiry > datetime.utcnow()
    ).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user.password_hash = hash_password(data.new_password)
    user.reset_token   = None
    user.reset_expiry  = None
    db.commit()
    return {"message": "Password reset successfully"}
