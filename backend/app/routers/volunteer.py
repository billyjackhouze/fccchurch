"""
Volunteer shift sign-up endpoints.
"""
from datetime import date as dt_date, datetime, timedelta
from typing import List, Optional
import os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app import models, schemas
from app.routers.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/shifts", tags=["Volunteer"])


def enrich_shift(shift: models.VolunteerShift, current_member_id: Optional[str] = None) -> schemas.VolunteerShiftOut:
    signups_out = []
    for s in shift.signups:
        if s.member:
            signups_out.append(schemas.ShiftSignupOut(
                id=s.id,
                member_id=s.member_id,
                member_name=f"{s.member.first} {s.member.last}",
                member_photo=s.member.photo,
                signed_up_at=s.signed_up_at,
            ))
    slots_filled = len(signups_out)
    slots_open   = max(0, (shift.slots_needed or 1) - slots_filled)
    is_signed_up = any(s.member_id == current_member_id for s in shift.signups) if current_member_id else False

    return schemas.VolunteerShiftOut(
        id=shift.id,
        title=shift.title,
        ministry=shift.ministry,
        date=shift.date,
        start_time=shift.start_time,
        end_time=shift.end_time,
        room_id=shift.room_id,
        room_name=shift.room.name if shift.room else None,
        location_notes=shift.location_notes,
        description=shift.description,
        slots_needed=shift.slots_needed,
        signups=signups_out,
        slots_filled=slots_filled,
        slots_open=slots_open,
        is_signed_up=is_signed_up,
        created_at=shift.created_at,
    )


def q_shifts(db):
    return db.query(models.VolunteerShift).options(
        joinedload(models.VolunteerShift.signups).joinedload(models.ShiftSignup.member),
        joinedload(models.VolunteerShift.room),
    )


# ── List shifts ───────────────────────────────────────────────────────────────

@router.get("", response_model=List[schemas.VolunteerShiftOut])
def list_shifts(
    ministry:   Optional[str]  = Query(None),
    month:      Optional[int]  = Query(None),
    year:       Optional[int]  = Query(None),
    open_only:  Optional[bool] = Query(False),
    from_date:  Optional[str]  = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = q_shifts(db)
    if ministry:
        q = q.filter(models.VolunteerShift.ministry == ministry)
    if year:
        from sqlalchemy import extract
        q = q.filter(extract('year', models.VolunteerShift.date) == year)
    if month:
        from sqlalchemy import extract
        q = q.filter(extract('month', models.VolunteerShift.date) == month)
    if from_date:
        q = q.filter(models.VolunteerShift.date >= from_date)
    shifts = q.order_by(models.VolunteerShift.date, models.VolunteerShift.start_time).all()
    mid = current_user.member_id
    result = [enrich_shift(s, mid) for s in shifts]
    if open_only:
        result = [s for s in result if s.slots_open > 0]
    return result


# ── My shifts ─────────────────────────────────────────────────────────────────

@router.get("/my", response_model=List[schemas.VolunteerShiftOut])
def my_shifts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.member_id:
        return []
    signups = db.query(models.ShiftSignup).filter(
        models.ShiftSignup.member_id == current_user.member_id
    ).all()
    shift_ids = [s.shift_id for s in signups]
    if not shift_ids:
        return []
    shifts = q_shifts(db).filter(
        models.VolunteerShift.id.in_(shift_ids)
    ).order_by(models.VolunteerShift.date, models.VolunteerShift.start_time).all()
    return [enrich_shift(s, current_user.member_id) for s in shifts]


# ── Get single shift ──────────────────────────────────────────────────────────

@router.get("/{shift_id}", response_model=schemas.VolunteerShiftOut)
def get_shift(
    shift_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    shift = q_shifts(db).filter(models.VolunteerShift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return enrich_shift(shift, current_user.member_id)


# ── Create shift (admin) ──────────────────────────────────────────────────────

@router.post("", response_model=schemas.VolunteerShiftOut, status_code=201)
def create_shift(
    data: schemas.VolunteerShiftCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    shift = models.VolunteerShift(**data.dict())
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return enrich_shift(q_shifts(db).filter(models.VolunteerShift.id == shift.id).first())


# ── Update shift (admin) ──────────────────────────────────────────────────────

@router.put("/{shift_id}", response_model=schemas.VolunteerShiftOut)
def update_shift(
    shift_id: str,
    data: schemas.VolunteerShiftUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    shift = db.query(models.VolunteerShift).filter(models.VolunteerShift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(shift, k, v)
    db.commit()
    return enrich_shift(q_shifts(db).filter(models.VolunteerShift.id == shift_id).first())


# ── Delete shift (admin) ──────────────────────────────────────────────────────

@router.delete("/{shift_id}", status_code=204)
def delete_shift(
    shift_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    shift = db.query(models.VolunteerShift).filter(models.VolunteerShift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    db.delete(shift)
    db.commit()


# ── Sign up for a shift ───────────────────────────────────────────────────────

@router.post("/{shift_id}/signup", response_model=schemas.VolunteerShiftOut)
def signup_for_shift(
    shift_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.member_id:
        raise HTTPException(status_code=400, detail="Your account is not linked to a member profile")
    shift = q_shifts(db).filter(models.VolunteerShift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    already = any(s.member_id == current_user.member_id for s in shift.signups)
    if already:
        raise HTTPException(status_code=400, detail="Already signed up for this shift")
    slots_filled = len(shift.signups)
    if slots_filled >= (shift.slots_needed or 1):
        raise HTTPException(status_code=400, detail="This shift is already full")
    signup = models.ShiftSignup(shift_id=shift_id, member_id=current_user.member_id)
    db.add(signup)
    db.commit()
    return enrich_shift(q_shifts(db).filter(models.VolunteerShift.id == shift_id).first(), current_user.member_id)


# ── Cancel signup ─────────────────────────────────────────────────────────────

@router.delete("/{shift_id}/signup", status_code=200)
def cancel_signup(
    shift_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.member_id:
        raise HTTPException(status_code=400, detail="Account not linked to a member profile")
    signup = db.query(models.ShiftSignup).filter(
        models.ShiftSignup.shift_id == shift_id,
        models.ShiftSignup.member_id == current_user.member_id,
    ).first()
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")
    db.delete(signup)
    db.commit()
    return {"message": "Signup cancelled"}


# ── Admin: remove any member from a shift ────────────────────────────────────

@router.delete("/{shift_id}/signup/{signup_id}", status_code=204)
def admin_remove_signup(
    shift_id: str,
    signup_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    signup = db.query(models.ShiftSignup).filter(
        models.ShiftSignup.id == signup_id,
        models.ShiftSignup.shift_id == shift_id,
    ).first()
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")
    db.delete(signup)
    db.commit()


# ── Send reminders for unfilled shifts ───────────────────────────────────────

@router.post("/reminders/send", tags=["Volunteer"])
def send_reminders(
    days_ahead: int = Query(7, description="Send reminders for shifts this many days away"),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Send email reminders to all members for shifts that still have open slots."""
    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        return {"message": "SMTP not configured — no emails sent", "shifts_checked": 0}

    target_date = dt_date.today() + timedelta(days=days_ahead)
    shifts = q_shifts(db).filter(
        models.VolunteerShift.date <= target_date,
        models.VolunteerShift.date >= dt_date.today(),
        models.VolunteerShift.reminder_sent == False,
    ).all()

    sent = 0
    base_url = os.getenv("APP_URL", "https://fcc.bjesoftware.com")

    for shift in shifts:
        slots_filled = len(shift.signups)
        if slots_filled >= (shift.slots_needed or 1):
            continue  # fully staffed

        # Get all active members with email
        members = db.query(models.Member).filter(
            models.Member.status == "Active",
            models.Member.email != None,
        ).all()

        # Filter by ministry if shift has one
        if shift.ministry:
            members = [m for m in members if m.ministry == shift.ministry]

        slots_open = (shift.slots_needed or 1) - slots_filled
        date_str = shift.date.strftime("%A, %B %d")
        time_str = ""
        if shift.start_time:
            h, m = shift.start_time.split(":")
            ap = "AM" if int(h) < 12 else "PM"
            h12 = int(h) % 12 or 12
            time_str = f" at {h12}:{m} {ap}"

        for member in members:
            # Skip if already signed up
            if any(s.member_id == member.id for s in shift.signups):
                continue
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"Volunteer needed: {shift.title} — {date_str}"
                msg["From"]    = os.getenv("SMTP_FROM", "noreply@fcc.bjesoftware.com")
                msg["To"]      = member.email

                body = (
                    f"Hi {member.first},\n\n"
                    f"We still need {slots_open} volunteer(s) for an upcoming shift:\n\n"
                    f"  {shift.title}\n"
                    f"  {date_str}{time_str}\n"
                    f"  {shift.location_notes or (shift.room.name if shift.room else 'Location TBD')}\n\n"
                    f"Sign up here: {base_url}\n\n"
                    f"Thank you for serving!\n— FFC Church"
                )
                msg.attach(MIMEText(body, "plain"))

                with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "587"))) as s:
                    s.starttls()
                    s.login(os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASS", ""))
                    s.send_message(msg)
                sent += 1
            except Exception as ex:
                print(f"Email failed for {member.email}: {ex}")

        shift.reminder_sent = True
    db.commit()

    return {"message": f"Reminders sent", "emails_sent": sent, "shifts_processed": len(shifts)}
