"""
Pydantic schemas for request validation and response serialization.
"""
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, EmailStr


# ── Members ───────────────────────────────────────────────────────────────────

class MemberBase(BaseModel):
    first:       str
    last:        str
    email:       Optional[str] = None
    phone:       Optional[str] = None
    address:     Optional[str] = None
    status:      Optional[str] = "Active"
    since:       Optional[date] = None
    ministry:    Optional[str] = None
    family_size: Optional[int] = 1
    notes:       Optional[str] = None

class MemberCreate(MemberBase):
    pass

class MemberUpdate(MemberBase):
    first: Optional[str] = None
    last:  Optional[str] = None

class MemberOut(MemberBase):
    id:         str
    created_at: datetime
    class Config:
        from_attributes = True


# ── Rooms ─────────────────────────────────────────────────────────────────────

class RoomBase(BaseModel):
    name:     str
    capacity: Optional[int] = 0
    location: Optional[str] = None
    features: Optional[str] = None
    notes:    Optional[str] = None
    color:    Optional[str] = "blue"

class RoomCreate(RoomBase):
    pass

class RoomUpdate(RoomBase):
    name: Optional[str] = None

class RoomOut(RoomBase):
    id:         str
    created_at: datetime
    class Config:
        from_attributes = True


# ── Events ────────────────────────────────────────────────────────────────────

class EventBase(BaseModel):
    title:           str
    date:            date
    start_time:      Optional[str] = None
    end_time:        Optional[str] = None
    type:            Optional[str] = "Event"
    room_id:         Optional[str] = None
    organizer:       Optional[str] = None
    description:     Optional[str] = None
    volunteer_slots: Optional[int] = 0

class EventCreate(EventBase):
    pass

class EventUpdate(EventBase):
    title: Optional[str] = None
    date:  Optional[date] = None

class EventOut(EventBase):
    id:         str
    created_at: datetime
    room_name:  Optional[str] = None  # Joined from rooms table
    class Config:
        from_attributes = True


# ── Giving ────────────────────────────────────────────────────────────────────

class GivingBase(BaseModel):
    member_id: Optional[str] = None
    date:      date
    amount:    Decimal
    type:      Optional[str] = "Tithe"
    fund:      Optional[str] = "General Fund"
    notes:     Optional[str] = None

class GivingCreate(GivingBase):
    pass

class GivingOut(GivingBase):
    id:          str
    member_name: Optional[str] = None  # Joined from members table
    created_at:  datetime
    class Config:
        from_attributes = True


# ── Pledges ───────────────────────────────────────────────────────────────────

class PledgeBase(BaseModel):
    member_id:      Optional[str] = None
    campaign:       Optional[str] = "General Pledge"
    pledged_amount: Decimal
    paid_amount:    Optional[Decimal] = Decimal("0")
    pledge_date:    Optional[date] = None
    end_date:       Optional[date] = None
    frequency:      Optional[str] = "One-time"
    status:         Optional[str] = "Active"

class PledgeCreate(PledgeBase):
    pass

class PledgeUpdate(BaseModel):
    paid_amount: Optional[Decimal] = None
    status:      Optional[str] = None
    end_date:    Optional[date] = None

class PledgeOut(PledgeBase):
    id:          str
    member_name: Optional[str] = None
    balance:     Optional[Decimal] = None
    created_at:  datetime
    class Config:
        from_attributes = True


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    active_members:    int
    total_members:     int
    upcoming_events:   int
    month_giving:      Decimal
    total_pledged:     Decimal
    total_paid:        Decimal
    pledge_pct:        int
