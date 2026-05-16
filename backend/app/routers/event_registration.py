"""
Event Registration router — public sign-up + admin management.

Public (no auth):
  GET  /api/event-reg/{event_id}/public      – event details for registration page
  POST /api/event-reg/{event_id}/register    – submit a registration

Admin:
  GET    /api/event-reg/{event_id}/registrations         – list registrations
  GET    /api/event-reg/{event_id}/registrations/export  – CSV download
  DELETE /api/event-reg/{event_id}/registrations/{reg_id}
  PATCH  /api/event-reg/{event_id}/settings              – update reg settings
  GET    /api/event-reg/all                              – all events with reg counts
"""

import csv
import io
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.routers.auth import require_admin

router = APIRouter(prefix="/api/event-reg", tags=["EventRegistration"])


# ── SMTP helpers (mirrors communications.py) ──────────────────────────────────

def _get_smtp(db: Session) -> dict:
    keys = ["smtp_host", "smtp_port", "smtp_username", "smtp_password",
            "smtp_use_tls", "smtp_from_name", "smtp_from_address"]
    return {r.key: r.value for r in db.query(models.Setting).filter(
        models.Setting.key.in_(keys)).all()}


def _send_confirmation(smtp_cfg: dict, to_email: str, to_name: str, event) -> None:
    host     = smtp_cfg.get("smtp_host", "")
    port     = int(smtp_cfg.get("smtp_port", 587))
    username = smtp_cfg.get("smtp_username", "")
    password = smtp_cfg.get("smtp_password", "")
    use_tls  = smtp_cfg.get("smtp_use_tls", "true").lower() == "true"
    from_name = smtp_cfg.get("smtp_from_name", "FFC Church")
    from_addr = smtp_cfg.get("smtp_from_address", username)

    if not host or not username:
        return  # SMTP not configured

    date_str = event.date.strftime("%B %d, %Y") if event.date else ""
    time_str = ""
    if event.start_time:
        time_str = f" at {event.start_time}"
        if event.end_time:
            time_str += f"–{event.end_time}"

    body_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:'Segoe UI',Arial,sans-serif;background:#F0F4F8;margin:0;padding:20px">
<div style="max-width:580px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)">
  <div style="background:#1E3A5F;color:#fff;padding:24px 32px">
    <h1 style="margin:0;font-size:20px">FFC Church</h1>
    <p style="margin:4px 0 0;font-size:12px;color:#93C5FD">Event Registration Confirmation</p>
  </div>
  <div style="padding:28px 32px;color:#374151;font-size:14px;line-height:1.7">
    <p>Hi {to_name},</p>
    <p>You're all set! Your registration for <strong>{event.title}</strong> has been confirmed.</p>
    <div style="background:#F9FAFB;border-left:4px solid #1E3A5F;border-radius:0 6px 6px 0;padding:14px 18px;margin:18px 0">
      <div style="font-weight:700;font-size:15px;color:#1E3A5F;margin-bottom:6px">{event.title}</div>
      <div>📅 {date_str}{time_str}</div>
      {'<div>📝 ' + event.description[:200] + ('…' if len(event.description or '') > 200 else '') + '</div>' if event.description else ''}
    </div>
    <p>We look forward to seeing you there. If you have any questions, please contact us.</p>
    <p style="margin-top:24px">Blessings,<br><strong>FFC Church</strong></p>
  </div>
  <div style="background:#F3F4F6;padding:14px 32px;font-size:11px;color:#9CA3AF;text-align:center">
    FFC Church &bull; Family Fellowship Church
  </div>
</div>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Registered: {event.title} — {date_str}"
    msg["From"]    = f"{from_name} <{from_addr}>"
    msg["To"]      = f"{to_name} <{to_email}>"
    msg.attach(MIMEText(
        f"Hi {to_name},\n\nYou're registered for {event.title} on {date_str}{time_str}.\n\nBlessings,\nFFC Church",
        "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=10) as server:
        if use_tls:
            server.starttls()
        server.login(username, password)
        server.sendmail(from_addr, [to_email], msg.as_string())


# ── Public endpoints (no auth) ────────────────────────────────────────────────

@router.get("/all")
def all_events_with_reg(
    db: Session = Depends(get_db),
    _user = Depends(require_admin),
):
    """Admin — list all events with registration counts."""
    events = db.query(models.Event).order_by(models.Event.date.desc()).all()
    result = []
    for e in events:
        reg_count = len(e.registrations)
        result.append({
            "id":                   e.id,
            "title":                e.title,
            "date":                 e.date.isoformat(),
            "start_time":           e.start_time,
            "end_time":             e.end_time,
            "type":                 e.type,
            "organizer":            e.organizer,
            "description":          e.description,
            "registration_enabled": bool(e.registration_enabled),
            "registration_limit":   e.registration_limit or 0,
            "registration_note":    e.registration_note,
            "registration_count":   reg_count,
        })
    return result


@router.get("/{event_id}/public")
def get_event_public(event_id: str, db: Session = Depends(get_db)):
    """No auth — returns event info for the public registration page."""
    e = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not e:
        raise HTTPException(404, "Event not found")
    reg_count = len(e.registrations)
    return {
        "id":                   e.id,
        "title":                e.title,
        "date":                 e.date.isoformat(),
        "start_time":           e.start_time,
        "end_time":             e.end_time,
        "type":                 e.type,
        "organizer":            e.organizer,
        "description":          e.description,
        "registration_enabled": bool(e.registration_enabled),
        "registration_limit":   e.registration_limit or 0,
        "registration_note":    e.registration_note,
        "registration_count":   reg_count,
        "is_full": (e.registration_limit or 0) > 0 and reg_count >= (e.registration_limit or 0),
    }


@router.post("/{event_id}/register")
def register_for_event(event_id: str, payload: dict, db: Session = Depends(get_db)):
    """No auth — public event registration."""
    e = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not e:
        raise HTTPException(404, "Event not found")
    if not e.registration_enabled:
        raise HTTPException(400, "Registration is not open for this event")

    reg_count = len(e.registrations)
    if (e.registration_limit or 0) > 0 and reg_count >= e.registration_limit:
        raise HTTPException(400, "This event is full — no spots remaining")

    first = (payload.get("first") or "").strip()
    last  = (payload.get("last")  or "").strip()
    email = (payload.get("email") or "").strip()
    phone = (payload.get("phone") or "").strip()
    notes = (payload.get("notes") or "").strip()

    if not first or not last or not email:
        raise HTTPException(400, "First name, last name, and email are required")

    reg = models.EventRegistration(
        event_id=event_id, first=first, last=last,
        email=email, phone=phone, notes=notes,
    )
    db.add(reg)
    db.commit()

    # Confirmation email (best-effort)
    try:
        smtp_cfg = _get_smtp(db)
        _send_confirmation(smtp_cfg, email, f"{first} {last}", e)
    except Exception:
        pass

    return {"ok": True, "message": f"You're registered for {e.title}!"}


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.get("/{event_id}/registrations")
def list_registrations(
    event_id: str,
    db: Session = Depends(get_db),
    _u = Depends(require_admin),
):
    e = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not e:
        raise HTTPException(404, "Event not found")
    return [
        {
            "id":            r.id,
            "first":         r.first,
            "last":          r.last,
            "email":         r.email,
            "phone":         r.phone,
            "notes":         r.notes,
            "registered_at": r.registered_at.isoformat() if r.registered_at else None,
        }
        for r in sorted(e.registrations, key=lambda x: x.registered_at or datetime.min)
    ]


@router.get("/{event_id}/registrations/export")
def export_registrations(
    event_id: str,
    db: Session = Depends(get_db),
    _u = Depends(require_admin),
):
    e = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not e:
        raise HTTPException(404, "Event not found")

    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(["First", "Last", "Email", "Phone", "Notes", "Registered At"])
    for r in sorted(e.registrations, key=lambda x: x.registered_at or datetime.min):
        w.writerow([r.first, r.last, r.email, r.phone or "", r.notes or "",
                    r.registered_at.strftime("%Y-%m-%d %H:%M") if r.registered_at else ""])

    safe = e.title.replace(" ", "_").replace("/", "-")[:40]
    fname = f"registrations_{safe}_{e.date}.csv"
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.delete("/{event_id}/registrations/{reg_id}")
def delete_registration(
    event_id: str, reg_id: str,
    db: Session = Depends(get_db),
    _u = Depends(require_admin),
):
    reg = db.query(models.EventRegistration).filter(
        models.EventRegistration.id == reg_id,
        models.EventRegistration.event_id == event_id,
    ).first()
    if not reg:
        raise HTTPException(404, "Registration not found")
    db.delete(reg)
    db.commit()
    return {"ok": True}


@router.patch("/{event_id}/settings")
def update_settings(
    event_id: str, payload: dict,
    db: Session = Depends(get_db),
    _u = Depends(require_admin),
):
    e = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not e:
        raise HTTPException(404, "Event not found")
    if "registration_enabled" in payload:
        e.registration_enabled = bool(payload["registration_enabled"])
    if "registration_limit" in payload:
        e.registration_limit = int(payload.get("registration_limit") or 0)
    if "registration_note" in payload:
        e.registration_note = payload["registration_note"]
    db.commit()
    return {"ok": True}
