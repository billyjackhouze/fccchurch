"""
Attendance Tracking & Check-in Kiosk endpoints.

Admin endpoints (require login):
  GET    /api/attendance                    — list service records
  POST   /api/attendance                    — create a headcount record
  PUT    /api/attendance/{id}               — update headcount / notes
  DELETE /api/attendance/{id}               — delete record + checkins
  GET    /api/attendance/{id}/checkins      — list who checked in for a service
  POST   /api/attendance/checkins           — admin manually adds a checkin
  DELETE /api/attendance/checkins/{cid}     — remove a checkin
  GET    /api/attendance/stats              — dashboard trend data
  GET    /api/attendance/member/{member_id} — member's checkin history

Public kiosk endpoints (NO auth — tablet at church entrance):
  GET    /api/attendance/kiosk/today              — today's record + checkin count
  GET    /api/attendance/kiosk/status/{member_id} — is member checked in today?
  POST   /api/attendance/kiosk/checkin            — check a member in
"""
from typing import List, Optional
from datetime import date as dt_date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app import models, schemas
from app.routers.auth import require_admin, get_current_user

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _checkin_out(c: models.MemberCheckin) -> schemas.CheckinOut:
    return schemas.CheckinOut(
        id=c.id,
        member_id=c.member_id,
        member_name=(f"{c.member.first} {c.member.last}" if c.member else None),
        member_photo=(c.member.photo if c.member else None),
        date=c.date,
        checked_in_at=c.checked_in_at,
        method=c.method,
    )


def _record_out(r: models.AttendanceRecord, db: Session) -> schemas.AttendanceRecordOut:
    count = db.query(func.count(models.MemberCheckin.id)).filter(
        models.MemberCheckin.record_id == r.id).scalar() or 0
    return schemas.AttendanceRecordOut(
        id=r.id, date=r.date, service_type=r.service_type,
        headcount=r.headcount, notes=r.notes,
        checkin_count=count, created_at=r.created_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN endpoints
# ══════════════════════════════════════════════════════════════════════════════

@router.get("", response_model=List[schemas.AttendanceRecordOut])
def list_records(
    limit: int = Query(50),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    records = (db.query(models.AttendanceRecord)
               .order_by(models.AttendanceRecord.date.desc())
               .limit(limit).all())
    return [_record_out(r, db) for r in records]


@router.post("", response_model=schemas.AttendanceRecordOut, status_code=201)
def create_record(
    data: schemas.AttendanceRecordCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    r = models.AttendanceRecord(**data.dict())
    db.add(r)
    db.commit()
    db.refresh(r)
    return _record_out(r, db)


@router.put("/{record_id}", response_model=schemas.AttendanceRecordOut)
def update_record(
    record_id: str,
    data: schemas.AttendanceRecordUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    r = db.query(models.AttendanceRecord).filter(
        models.AttendanceRecord.id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Record not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(r, k, v)
    db.commit()
    return _record_out(r, db)


@router.delete("/{record_id}", status_code=204)
def delete_record(
    record_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    r = db.query(models.AttendanceRecord).filter(
        models.AttendanceRecord.id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(r)
    db.commit()


@router.get("/{record_id}/checkins", response_model=List[schemas.CheckinOut])
def list_checkins_for_record(
    record_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    checkins = (db.query(models.MemberCheckin)
                .options(joinedload(models.MemberCheckin.member))
                .filter(models.MemberCheckin.record_id == record_id)
                .order_by(models.MemberCheckin.checked_in_at)
                .all())
    return [_checkin_out(c) for c in checkins]


@router.post("/checkins", response_model=schemas.CheckinOut, status_code=201)
def admin_add_checkin(
    data: schemas.AdminCheckinCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    # Prevent duplicate on same day
    existing = db.query(models.MemberCheckin).filter(
        models.MemberCheckin.member_id == data.member_id,
        models.MemberCheckin.date == data.date,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Member already checked in for this date")
    c = models.MemberCheckin(
        member_id=data.member_id,
        date=data.date,
        record_id=data.record_id,
        method="admin",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    c = (db.query(models.MemberCheckin)
         .options(joinedload(models.MemberCheckin.member))
         .filter(models.MemberCheckin.id == c.id).first())
    return _checkin_out(c)


@router.delete("/checkins/{checkin_id}", status_code=204)
def remove_checkin(
    checkin_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    c = db.query(models.MemberCheckin).filter(
        models.MemberCheckin.id == checkin_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Checkin not found")
    db.delete(c)
    db.commit()


@router.get("/stats")
def attendance_stats(db: Session = Depends(get_db),
                     _: models.User = Depends(require_admin)):
    """
    Returns:
      - last 8 attendance records with checkin counts (for chart)
      - today's checkin count
      - this month average headcount
    """
    from datetime import date as dt_date
    today = dt_date.today()

    # Last 8 service records
    records = (db.query(models.AttendanceRecord)
               .order_by(models.AttendanceRecord.date.desc())
               .limit(8).all())
    history = []
    for r in records:
        cnt = db.query(func.count(models.MemberCheckin.id)).filter(
            models.MemberCheckin.record_id == r.id).scalar() or 0
        history.append({
            "date": str(r.date),
            "service_type": r.service_type,
            "headcount": r.headcount,
            "checkin_count": cnt,
        })

    # Today's checkins
    today_count = db.query(func.count(models.MemberCheckin.id)).filter(
        models.MemberCheckin.date == today).scalar() or 0

    # Most recent record
    latest = records[0] if records else None
    latest_checkins = history[0]["checkin_count"] if history else 0

    return {
        "history": list(reversed(history)),
        "today_checkins": today_count,
        "latest_record": {
            "date": str(latest.date) if latest else None,
            "service_type": latest.service_type if latest else None,
            "headcount": latest.headcount if latest else 0,
            "checkin_count": latest_checkins,
        } if latest else None,
    }


@router.get("/member/{member_id}")
def member_attendance_history(
    member_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """Checkin history for a specific member (for profile page)."""
    from datetime import timedelta
    today = dt_date.today()
    ninety_days_ago = today - timedelta(days=90)

    checkins = (db.query(models.MemberCheckin)
                .filter(models.MemberCheckin.member_id == member_id)
                .order_by(models.MemberCheckin.date.desc())
                .all())

    # Attendance % vs total services in last 90 days
    total_services = db.query(func.count(models.AttendanceRecord.id)).filter(
        models.AttendanceRecord.date >= ninety_days_ago).scalar() or 0
    recent_checkins = sum(1 for c in checkins if c.date >= ninety_days_ago)
    pct = int(recent_checkins / total_services * 100) if total_services > 0 else None

    return {
        "checkins": [{"id": c.id, "date": str(c.date),
                      "checked_in_at": str(c.checked_in_at), "method": c.method}
                     for c in checkins],
        "total": len(checkins),
        "recent_90_days": recent_checkins,
        "total_services_90_days": total_services,
        "attendance_pct": pct,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC KIOSK endpoints — NO authentication required
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/kiosk/today")
def kiosk_today(db: Session = Depends(get_db)):
    """Return today's attendance record (if any) and total checkin count for today."""
    today = dt_date.today()
    record = (db.query(models.AttendanceRecord)
              .filter(models.AttendanceRecord.date == today)
              .first())
    checkin_count = db.query(func.count(models.MemberCheckin.id)).filter(
        models.MemberCheckin.date == today).scalar() or 0
    return {
        "record": {
            "id": record.id,
            "service_type": record.service_type,
            "headcount": record.headcount,
        } if record else None,
        "checkin_count": checkin_count,
        "date": str(today),
    }


@router.get("/kiosk/status/{member_id}")
def kiosk_member_status(member_id: str, db: Session = Depends(get_db)):
    """Check if a member has already checked in today."""
    today = dt_date.today()
    checkin = db.query(models.MemberCheckin).filter(
        models.MemberCheckin.member_id == member_id,
        models.MemberCheckin.date == today,
    ).first()
    return {
        "checked_in": checkin is not None,
        "checked_in_at": str(checkin.checked_in_at) if checkin else None,
    }


@router.post("/kiosk/checkin")
def kiosk_checkin(body: dict, db: Session = Depends(get_db)):
    """
    Public endpoint — check a member in via the kiosk tablet.
    Body: { member_id: str, record_id?: str }
    Returns: { success, already_checked_in, checkin_count }
    """
    member_id = body.get("member_id")
    record_id = body.get("record_id")
    if not member_id:
        raise HTTPException(status_code=400, detail="member_id required")

    today = dt_date.today()

    # Verify member exists
    member = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Already checked in?
    existing = db.query(models.MemberCheckin).filter(
        models.MemberCheckin.member_id == member_id,
        models.MemberCheckin.date == today,
    ).first()
    if existing:
        count = db.query(func.count(models.MemberCheckin.id)).filter(
            models.MemberCheckin.date == today).scalar() or 0
        return {
            "success": True,
            "already_checked_in": True,
            "member_name": f"{member.first} {member.last}",
            "checkin_count": count,
        }

    # Create checkin
    c = models.MemberCheckin(
        member_id=member_id,
        date=today,
        record_id=record_id or None,
        method="kiosk",
    )
    db.add(c)
    db.commit()

    count = db.query(func.count(models.MemberCheckin.id)).filter(
        models.MemberCheckin.date == today).scalar() or 0

    return {
        "success": True,
        "already_checked_in": False,
        "member_name": f"{member.first} {member.last}",
        "member_photo": member.photo,
        "checkin_count": count,
    }
