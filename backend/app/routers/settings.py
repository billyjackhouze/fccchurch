"""
App-wide settings — email credentials, API keys, value lists.
All write endpoints are admin-only. Secrets are masked on read.
"""
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.routers.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/settings", tags=["Settings"])

# ── Default setting definitions ───────────────────────────────────────────────
DEFAULTS = [
    # group, key, label, is_secret, default_value
    ("general", "church_name",       "Church Name",               False, "FFC Church"),
    ("general", "church_address",    "Address",                   False, ""),
    ("general", "church_phone",      "Phone",                     False, ""),
    ("general", "church_website",    "Website",                   False, ""),

    ("email",   "email_smtp_host",   "SMTP Host",                 False, "smtp.gmail.com"),
    ("email",   "email_smtp_port",   "SMTP Port",                 False, "587"),
    ("email",   "email_smtp_user",   "SMTP Username",             False, ""),
    ("email",   "email_smtp_pass",   "SMTP Password",             True,  ""),
    ("email",   "email_from_name",   "From Name",                 False, "FFC Church"),
    ("email",   "email_from_addr",   "From Address",              False, ""),
    ("email",   "email_use_tls",     "Use TLS",                   False, "true"),

    ("api",     "api_anthropic_key", "Anthropic API Key",         True,  ""),

    ("lists",   "list_member_status",
     "Member Status Options",  False,
     json.dumps(["Active", "Inactive", "Guest", "Visitor", "Former Member"])),

    ("lists",   "list_event_types",
     "Event Types",            False,
     json.dumps(["Sunday Service", "Wednesday Service", "Bible Study",
                 "Prayer Meeting", "Special Event", "Youth Event",
                 "Community Outreach", "Meeting", "Other"])),

    ("lists",   "list_giving_types",
     "Giving Types",           False,
     json.dumps(["Tithe", "Offering", "Special Gift", "Building Fund",
                 "Missions", "Memorial", "Other"])),

    ("lists",   "list_giving_funds",
     "Giving Funds",           False,
     json.dumps(["General Fund", "Building Fund", "Missions Fund",
                 "Youth Fund", "Benevolence Fund"])),

    ("lists",   "list_service_item_types",
     "Service Item Types",     False,
     json.dumps(["Song", "Sermon", "Prayer", "Announcement",
                 "Communion", "Offering", "Scripture Reading",
                 "Welcome", "Dismissal", "Other"])),
]


def seed_defaults(db: Session):
    """Insert any missing settings with their default values."""
    for group, key, label, is_secret, default in DEFAULTS:
        existing = db.query(models.Setting).filter(models.Setting.key == key).first()
        if not existing:
            db.add(models.Setting(
                key=key, value=default, is_secret=is_secret,
                label=label, group=group,
            ))
    db.commit()


def mask(s: models.Setting) -> schemas.SettingOut:
    return schemas.SettingOut(
        key=s.key,
        value="***" if s.is_secret and s.value else s.value,
        is_secret=s.is_secret,
        label=s.label,
        group=s.group,
    )


# ── List all settings (admin) ─────────────────────────────────────────────────

@router.get("", response_model=List[schemas.SettingOut])
def list_settings(db: Session = Depends(get_db),
                  _: models.User = Depends(require_admin)):
    seed_defaults(db)
    settings = db.query(models.Setting).order_by(
        models.Setting.group, models.Setting.key).all()
    return [mask(s) for s in settings]


# ── Get one setting (admin) ───────────────────────────────────────────────────

@router.get("/{key}", response_model=schemas.SettingOut)
def get_setting(key: str, db: Session = Depends(get_db),
                _: models.User = Depends(require_admin)):
    s = db.query(models.Setting).filter(models.Setting.key == key).first()
    if not s:
        raise HTTPException(status_code=404, detail="Setting not found")
    return mask(s)


# ── Upsert a setting (admin) ──────────────────────────────────────────────────

@router.put("/{key}", response_model=schemas.SettingOut)
def upsert_setting(key: str, body: schemas.SettingUpsert,
                   db: Session = Depends(get_db),
                   _: models.User = Depends(require_admin)):
    s = db.query(models.Setting).filter(models.Setting.key == key).first()
    if not s:
        # Find metadata from DEFAULTS
        meta = next((d for d in DEFAULTS if d[1] == key), None)
        if not meta:
            raise HTTPException(status_code=404, detail="Unknown setting key")
        s = models.Setting(key=key, group=meta[0], label=meta[2], is_secret=meta[3])
        db.add(s)
    s.value = body.value
    db.commit()
    return mask(s)


# ── Internal helper: read raw value (no mask) ─────────────────────────────────

def get_raw(key: str, db: Session) -> str:
    """Read a raw (unmasked) setting value. Used internally by other routers."""
    s = db.query(models.Setting).filter(models.Setting.key == key).first()
    return s.value if s else ""
