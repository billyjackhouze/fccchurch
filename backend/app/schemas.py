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
    pronouns:    Optional[str] = None
    notes:       Optional[str] = None
    photo:       Optional[str] = None

class MemberCreate(MemberBase):
    pass

class MemberUpdate(MemberBase):
    first: Optional[str] = None
    last:  Optional[str] = None

class MemberRelationshipCreate(BaseModel):
    related_id: str
    relation:   str

class MemberRelationshipOut(BaseModel):
    id:           str
    related_id:   str
    related_name: str
    relation:     str
    related_photo: Optional[str] = None
    class Config:
        from_attributes = True

class MemberOut(MemberBase):
    id:            str
    created_at:    datetime
    family:        Optional[List[MemberRelationshipOut]] = []
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
    room_name:  Optional[str] = None
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
    member_name: Optional[str] = None
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


# ── Auth / Users ──────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email:     str
    password:  str
    role:      Optional[str] = "member"
    member_id: Optional[str] = None

class UserUpdate(BaseModel):
    email:     Optional[str] = None
    password:  Optional[str] = None
    role:      Optional[str] = None
    is_active: Optional[bool] = None
    member_id: Optional[str] = None

class UserOut(BaseModel):
    id:        str
    email:     str
    role:      str
    is_active: bool
    member_id: Optional[str] = None
    member_name: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class TokenOut(BaseModel):
    access_token: str
    token_type:   str
    role:         str
    user_id:      str
    member_id:    Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password:     str

class ForgotPassword(BaseModel):
    email: str

class ResetPassword(BaseModel):
    token:        str
    new_password: str


# ── Ministries ────────────────────────────────────────────────────────────────

class MinistryMembershipOut(BaseModel):
    id:           str
    member_id:    str
    member_name:  str
    member_photo: Optional[str] = None
    role:         str
    joined_date:  Optional[date] = None
    class Config:
        from_attributes = True

class MinistryBase(BaseModel):
    name:        str
    description: Optional[str] = None
    leader_id:   Optional[str] = None
    color:       Optional[str] = "blue"

class MinistryCreate(MinistryBase):
    pass

class MinistryUpdate(MinistryBase):
    name: Optional[str] = None

class MinistryOut(MinistryBase):
    id:           str
    leader_name:  Optional[str] = None
    member_count: int = 0
    memberships:  List[MinistryMembershipOut] = []
    created_at:   datetime
    class Config:
        from_attributes = True

class MinistryMembershipCreate(BaseModel):
    member_id:   str
    role:        Optional[str] = "Member"
    joined_date: Optional[date] = None


# ── Service Planning ──────────────────────────────────────────────────────────

class ServiceItemBase(BaseModel):
    item_type:        Optional[str] = "other"
    title:            str
    duration_minutes: Optional[int] = 5
    notes:            Optional[str] = None
    color:            Optional[str] = "blue"
    sort_order:       Optional[int] = 0

class ServiceItemCreate(ServiceItemBase):
    pass

class ServiceItemUpdate(ServiceItemBase):
    title: Optional[str] = None

class ServiceItemOut(ServiceItemBase):
    id:         str
    plan_id:    str
    created_at: datetime
    class Config:
        from_attributes = True

class ServiceItemReorder(BaseModel):
    ordered_ids: List[str]

class ServicePlanBase(BaseModel):
    title:            str
    date:             date
    service_type:     Optional[str] = "Sunday Service"
    status:           Optional[str] = "draft"
    series_name:      Optional[str] = None
    sermon_title:     Optional[str] = None
    sermon_scripture: Optional[str] = None
    sermon_notes:     Optional[str] = None
    preacher_id:      Optional[str] = None
    notes:            Optional[str] = None

class ServicePlanCreate(ServicePlanBase):
    pass

class ServicePlanUpdate(ServicePlanBase):
    title: Optional[str] = None
    date:  Optional[date] = None

class ServicePlanOut(ServicePlanBase):
    id:             str
    preacher_name:  Optional[str] = None
    items:          List[ServiceItemOut] = []
    item_count:     int = 0
    total_minutes:  int = 0
    created_at:     datetime
    class Config:
        from_attributes = True


# ── Org Hierarchy ─────────────────────────────────────────────────────────────

class OrgNodeBase(BaseModel):
    title:      str
    member_id:  Optional[str] = None
    parent_id:  Optional[str] = None
    sort_order: Optional[int] = 0
    notes:      Optional[str] = None

class OrgNodeCreate(OrgNodeBase):
    pass

class OrgNodeUpdate(OrgNodeBase):
    title: Optional[str] = None

class OrgNodeOut(OrgNodeBase):
    id:          str
    member_name: Optional[str] = None
    member_photo: Optional[str] = None
    children:    List["OrgNodeOut"] = []
    created_at:  datetime
    class Config:
        from_attributes = True

OrgNodeOut.model_rebuild()


# ── Groups ─────────────────────────────────────────────────────────────────────

class GroupMembershipOut(BaseModel):
    id:           str
    member_id:    str
    member_name:  str
    member_photo: Optional[str] = None
    role:         str
    joined_date:  Optional[date] = None
    class Config:
        from_attributes = True

class GroupBase(BaseModel):
    name:         str
    group_type:   Optional[str] = "Small Group"
    leader_id:    Optional[str] = None
    meeting_day:  Optional[str] = None
    meeting_time: Optional[str] = None
    location:     Optional[str] = None
    description:  Optional[str] = None
    is_active:    Optional[bool] = True
    color:        Optional[str] = "blue"

class GroupCreate(GroupBase):
    pass

class GroupUpdate(GroupBase):
    name: Optional[str] = None

class GroupOut(GroupBase):
    id:           str
    leader_name:  Optional[str] = None
    member_count: int = 0
    memberships:  List[GroupMembershipOut] = []
    created_at:   datetime
    class Config:
        from_attributes = True

class GroupMembershipCreate(BaseModel):
    member_id:   str
    role:        Optional[str] = "Member"
    joined_date: Optional[date] = None


# ── Volunteer Shifts ──────────────────────────────────────────────────────────

class ShiftSignupOut(BaseModel):
    id:           str
    member_id:    str
    member_name:  str
    member_photo: Optional[str] = None
    signed_up_at: datetime
    class Config:
        from_attributes = True

class VolunteerShiftBase(BaseModel):
    title:          str
    ministry:       Optional[str] = None
    date:           date
    start_time:     Optional[str] = None
    end_time:       Optional[str] = None
    room_id:        Optional[str] = None
    location_notes: Optional[str] = None
    description:    Optional[str] = None
    slots_needed:   Optional[int] = 1

class VolunteerShiftCreate(VolunteerShiftBase):
    pass

class VolunteerShiftUpdate(VolunteerShiftBase):
    title: Optional[str] = None
    date:  Optional[date] = None

class VolunteerShiftOut(VolunteerShiftBase):
    id:           str
    room_name:    Optional[str] = None
    signups:      List[ShiftSignupOut] = []
    slots_filled: int = 0
    slots_open:   int = 0
    is_signed_up: bool = False
    created_at:   datetime
    class Config:
        from_attributes = True


# ── Sermons ───────────────────────────────────────────────────────────────────

class SermonBase(BaseModel):
    title:        str
    date:         date
    series_name:  Optional[str] = None
    scripture:    Optional[str] = None
    preacher_id:  Optional[str] = None
    plan_id:      Optional[str] = None
    sermon_notes: Optional[str] = None
    tags:         Optional[str] = None
    outline_json: Optional[str] = None

class SermonCreate(SermonBase):
    pass

class SermonUpdate(SermonBase):
    title: Optional[str] = None
    date:  Optional[date] = None

class SermonOut(SermonBase):
    id:            str
    preacher_name: Optional[str] = None
    plan_title:    Optional[str] = None
    created_at:    datetime
    class Config:
        from_attributes = True


# ── Settings ──────────────────────────────────────────────────────────────────

class SettingOut(BaseModel):
    key:       str
    value:     Optional[str] = None   # None / "***" for secrets
    is_secret: bool = False
    label:     Optional[str] = None
    group:     Optional[str] = None
    class Config:
        from_attributes = True

class SettingUpsert(BaseModel):
    value: str
