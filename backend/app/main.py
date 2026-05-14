"""
FFC Church Management System — FastAPI Backend
"""
from datetime import datetime, date
from decimal import Decimal
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
import os

from app.database import engine, get_db, Base
from app import models, schemas
from app.routers import members, events, rooms, giving, pledges
from app.routers import auth, users, volunteer, ministries, hierarchy, groups, service_plans

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FFC Church Management API",
    description="Church management system for FFC Church.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(members.router)
app.include_router(events.router)
app.include_router(rooms.router)
app.include_router(giving.router)
app.include_router(pledges.router)
app.include_router(volunteer.router)
app.include_router(ministries.router)
app.include_router(hierarchy.router)
app.include_router(groups.router)
app.include_router(service_plans.router)

# ── Static files (member photos) ──────────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
PHOTOS_DIR = os.path.join(STATIC_DIR, "photos")
os.makedirs(PHOTOS_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Dashboard endpoint ────────────────────────────────────────────────────────
@app.get("/api/dashboard", response_model=schemas.DashboardStats, tags=["Dashboard"])
def dashboard(db: Session = Depends(get_db)):
    today = date.today()
    now_y = today.year
    now_m = today.month

    active_members  = db.query(func.count(models.Member.id)).filter(models.Member.status == "Active").scalar() or 0
    total_members   = db.query(func.count(models.Member.id)).scalar() or 0
    upcoming_events = db.query(func.count(models.Event.id)).filter(models.Event.date >= today).scalar() or 0

    month_giving = db.query(func.sum(models.GivingRecord.amount)).filter(
        extract('year',  models.GivingRecord.date) == now_y,
        extract('month', models.GivingRecord.date) == now_m,
    ).scalar() or Decimal("0")

    total_pledged = db.query(func.sum(models.Pledge.pledged_amount)).scalar() or Decimal("0")
    total_paid    = db.query(func.sum(models.Pledge.paid_amount)).scalar()    or Decimal("0")
    pledge_pct    = int(total_paid / total_pledged * 100) if total_pledged > 0 else 0

    return schemas.DashboardStats(
        active_members=active_members,
        total_members=total_members,
        upcoming_events=upcoming_events,
        month_giving=month_giving,
        total_pledged=total_pledged,
        total_paid=total_paid,
        pledge_pct=pledge_pct,
    )


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["System"])
def health():
    return {"status": "ok", "app": "FFC Church Management", "version": "1.1.0"}


# ── Serve frontend (production) ───────────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
