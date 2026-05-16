"""
Bulk email communications router.

Endpoints
---------
POST  /api/comms/send              – resolve recipients, send emails, persist log
GET   /api/comms                   – list all communications (summary)
GET   /api/comms/{id}              – communication detail + recipient list
GET   /api/comms/track/{token}     – tracking-pixel endpoint (marks opened)
DELETE /api/comms/{id}             – delete a communication record
GET   /api/comms/preview-recipients – dry-run: return who would receive the email
"""

import json, uuid, smtplib, base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app import models
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/comms", tags=["Communications"])

# ── 1x1 transparent GIF for tracking pixel ────────────────────────────────────
PIXEL_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_smtp_settings(db: Session) -> dict:
    keys = ["smtp_host", "smtp_port", "smtp_username", "smtp_password",
            "smtp_use_tls", "smtp_from_name", "smtp_from_address"]
    rows = {r.key: r.value for r in db.query(models.Setting).filter(
        models.Setting.key.in_(keys)).all()}
    return rows


def _resolve_recipients(db: Session, filter_params: dict) -> List[models.Member]:
    """Return a list of Member rows matching the filter."""
    q = db.query(models.Member).filter(models.Member.email != None,
                                        models.Member.email != "")
    ftype = filter_params.get("type", "all")

    if ftype == "status":
        status = filter_params.get("value", "Active")
        q = q.filter(models.Member.status == status)

    elif ftype == "ministry":
        ministry = filter_params.get("value", "")
        q = q.filter(models.Member.ministry == ministry)

    elif ftype == "group":
        group_id = filter_params.get("value", "")
        member_ids = [gm.member_id for gm in
                      db.query(models.GroupMembership).filter(
                          models.GroupMembership.group_id == group_id).all()]
        q = q.filter(models.Member.id.in_(member_ids))

    elif ftype == "event":
        event_id = filter_params.get("value", "")
        checkin_dates = [e.date for e in
                         db.query(models.Event).filter(
                             models.Event.id == event_id).all()]
        if checkin_dates:
            d = checkin_dates[0]
            member_ids = [c.member_id for c in
                          db.query(models.MemberCheckin).filter(
                              models.MemberCheckin.date == d).all()]
            q = q.filter(models.Member.id.in_(member_ids))
        else:
            return []

    elif ftype == "members":
        ids = filter_params.get("value", [])
        if isinstance(ids, str):
            ids = ids.split(",")
        q = q.filter(models.Member.id.in_(ids))

    elif ftype == "volunteer_shift":
        shift_id = filter_params.get("value", "")
        member_ids = [s.member_id for s in
                      db.query(models.VolunteerSignup).filter(
                          models.VolunteerSignup.shift_id == shift_id).all()]
        q = q.filter(models.Member.id.in_(member_ids))

    # default: all members with email
    return q.order_by(models.Member.last, models.Member.first).all()


def _label_for_filter(db: Session, fp: dict) -> str:
    ftype = fp.get("type", "all")
    val   = fp.get("value", "")
    if ftype == "all":      return "All members with email"
    if ftype == "status":   return f"Status: {val}"
    if ftype == "ministry": return f"Ministry: {val}"
    if ftype == "group":
        g = db.query(models.Group).filter(models.Group.id == val).first()
        return f"Group: {g.name}" if g else f"Group: {val}"
    if ftype == "event":
        e = db.query(models.Event).filter(models.Event.id == val).first()
        return f"Event attendees: {e.title}" if e else f"Event: {val}"
    if ftype == "volunteer_shift":
        s = db.query(models.VolunteerShift).filter(models.VolunteerShift.id == val).first()
        return f"Volunteer shift: {s.title}" if s else f"Shift: {val}"
    if ftype == "members":  return "Selected members"
    return ftype


def _build_html(subject: str, body_html: str, track_url: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#F0F4F8;margin:0;padding:20px}}
.wrap{{max-width:620px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)}}
.header{{background:#1E3A5F;color:#fff;padding:24px 32px}}
.header h1{{margin:0;font-size:20px;font-weight:800}}
.header p{{margin:4px 0 0;font-size:12px;color:#93C5FD}}
.body{{padding:28px 32px;color:#374151;font-size:14px;line-height:1.7}}
.footer{{background:#F3F4F6;padding:16px 32px;font-size:11px;color:#9CA3AF;text-align:center}}
</style></head>
<body>
<div class="wrap">
  <div class="header">
    <h1>FFC Church</h1>
    <p>Family Fellowship Church</p>
  </div>
  <div class="body">{body_html}</div>
  <div class="footer">FFC Church &bull; You are receiving this because you are a member or friend of FFC Church.</div>
</div>
<img src="{track_url}" width="1" height="1" alt="" style="display:none">
</body></html>"""


def _send_email(smtp_cfg: dict, to_email: str, to_name: str,
                subject: str, body_html: str, body_text: str) -> None:
    host     = smtp_cfg.get("smtp_host", "")
    port     = int(smtp_cfg.get("smtp_port", 587))
    username = smtp_cfg.get("smtp_username", "")
    password = smtp_cfg.get("smtp_password", "")
    use_tls  = smtp_cfg.get("smtp_use_tls", "true").lower() == "true"
    from_name= smtp_cfg.get("smtp_from_name", "FFC Church")
    from_addr= smtp_cfg.get("smtp_from_address", username)

    if not host or not username:
        raise ValueError("SMTP not configured. Set SMTP settings in Admin Settings.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{from_name} <{from_addr}>"
    msg["To"]      = f"{to_name} <{to_email}>" if to_name else to_email

    msg.attach(MIMEText(body_text or "Please view this email in an HTML-capable client.", "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=15) as server:
        if use_tls:
            server.starttls()
        server.login(username, password)
        server.sendmail(from_addr, [to_email], msg.as_string())


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/track/{token}")
def track_open(token: str, db: Session = Depends(get_db)):
    """Tracking pixel — called when recipient opens the email."""
    rec = db.query(models.CommunicationRecipient).filter(
        models.CommunicationRecipient.track_token == token).first()
    if rec:
        now = datetime.utcnow()
        if rec.opened_at is None:
            rec.opened_at = now
            # increment communication opened_count
            comm = db.query(models.Communication).filter(
                models.Communication.id == rec.communication_id).first()
            if comm:
                comm.opened_count = (comm.opened_count or 0) + 1
        rec.open_count = (rec.open_count or 0) + 1
        db.commit()
    return Response(content=PIXEL_GIF,
                    media_type="image/gif",
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate",
                             "Pragma": "no-cache"})


@router.get("/preview-recipients")
def preview_recipients(
    filter_type:  str = Query("all"),
    filter_value: str = Query(""),
    db: Session = Depends(get_db),
    _user = Depends(get_current_user),
):
    fp = {"type": filter_type, "value": filter_value}
    members = _resolve_recipients(db, fp)
    return [{"id": m.id, "name": f"{m.first} {m.last}", "email": m.email,
             "ministry": m.ministry, "status": m.status} for m in members]


@router.post("/send")
def send_communication(
    payload: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    payload: {
      subject: str,
      body_html: str,
      body_text: str (optional),
      filter_type: str,   # all | status | ministry | group | event | members | volunteer_shift
      filter_value: str,  # depends on type
      base_url: str       # e.g. "https://fcc.bjesoftware.com" for tracking pixel
    }
    """
    try:
        subject      = payload.get("subject", "").strip()
        body_html    = payload.get("body_html", "").strip()
        body_text    = payload.get("body_text", "").strip()
        filter_type  = payload.get("filter_type", "all")
        filter_value = payload.get("filter_value", "")
        base_url     = payload.get("base_url", "").rstrip("/")

        if not subject:
            raise HTTPException(400, "Subject is required")
        if not body_html:
            raise HTTPException(400, "Email body is required")

        fp = {"type": filter_type, "value": filter_value}
        members = _resolve_recipients(db, fp)

        if not members:
            raise HTTPException(400, "No recipients found for the selected filter")

        smtp_cfg = _get_smtp_settings(db)

        # Create communication record
        comm = models.Communication(
            subject         = subject,
            body_html       = body_html,
            body_text       = body_text,
            filter_label    = _label_for_filter(db, fp),
            filter_json     = json.dumps(fp),
            sent_by_id      = current_user.id,
            recipient_count = len(members),
            opened_count    = 0,
        )
        db.add(comm)
        db.flush()  # get comm.id

        sent_count = 0
        errors     = []

        for m in members:
            token = uuid.uuid4().hex
            track_url = f"{base_url}/api/comms/track/{token}" if base_url else ""

            html = _build_html(subject, body_html, track_url)

            rec = models.CommunicationRecipient(
                communication_id = comm.id,
                member_id        = m.id,
                email            = m.email,
                name             = f"{m.first} {m.last}",
                track_token      = token,
            )
            db.add(rec)

            try:
                _send_email(smtp_cfg, m.email, f"{m.first} {m.last}", subject, html, body_text)
                sent_count += 1
            except Exception as e:
                errors.append({"email": m.email, "error": str(e)})

        db.commit()

        return {
            "communication_id": comm.id,
            "total_recipients": len(members),
            "sent": sent_count,
            "errors": errors,
            "filter_label": comm.filter_label,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=f"Send failed: {type(exc).__name__}: {exc}")


@router.get("")
def list_communications(
    db: Session = Depends(get_db),
    _user = Depends(get_current_user),
):
    comms = db.query(models.Communication).order_by(
        models.Communication.sent_at.desc()).all()
    result = []
    for c in comms:
        open_pct = round(c.opened_count / c.recipient_count * 100) if c.recipient_count else 0
        result.append({
            "id":              c.id,
            "subject":         c.subject,
            "filter_label":    c.filter_label,
            "sent_at":         c.sent_at.isoformat() if c.sent_at else None,
            "recipient_count": c.recipient_count,
            "opened_count":    c.opened_count,
            "open_pct":        open_pct,
            "sent_by_email":   c.sent_by.email if c.sent_by else None,
        })
    return result


@router.get("/{comm_id}")
def get_communication(
    comm_id: str,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user),
):
    c = db.query(models.Communication).filter(
        models.Communication.id == comm_id).first()
    if not c:
        raise HTTPException(404, "Communication not found")

    recipients = []
    for r in c.recipients:
        recipients.append({
            "id":         r.id,
            "member_id":  r.member_id,
            "name":       r.name,
            "email":      r.email,
            "opened_at":  r.opened_at.isoformat() if r.opened_at else None,
            "open_count": r.open_count,
        })

    open_pct = round(c.opened_count / c.recipient_count * 100) if c.recipient_count else 0

    return {
        "id":              c.id,
        "subject":         c.subject,
        "body_html":       c.body_html,
        "body_text":       c.body_text,
        "filter_label":    c.filter_label,
        "filter_json":     c.filter_json,
        "sent_at":         c.sent_at.isoformat() if c.sent_at else None,
        "sent_by_email":   c.sent_by.email if c.sent_by else None,
        "recipient_count": c.recipient_count,
        "opened_count":    c.opened_count,
        "open_pct":        open_pct,
        "recipients":      recipients,
    }


@router.delete("/{comm_id}")
def delete_communication(
    comm_id: str,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user),
):
    c = db.query(models.Communication).filter(
        models.Communication.id == comm_id).first()
    if not c:
        raise HTTPException(404, "Communication not found")
    db.delete(c)
    db.commit()
    return {"ok": True}
