"""
SQLAlchemy ORM models for FFC Church Management System.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


def gen_id():
    return str(uuid.uuid4())


class Member(Base):
    __tablename__ = "members"

    id          = Column(String, primary_key=True, default=gen_id)
    first       = Column(String(100), nullable=False)
    last        = Column(String(100), nullable=False)
    email       = Column(String(200))
    phone       = Column(String(30))
    address     = Column(String(300))
    status      = Column(String(20), default="Active")
    since       = Column(Date)
    ministry    = Column(String(200))
    family_size = Column(Integer, default=1)
    pronouns    = Column(String(50))
    notes       = Column(Text)
    photo       = Column(String(200))
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    giving      = relationship("GivingRecord",    back_populates="member", cascade="all, delete-orphan")
    pledges     = relationship("Pledge",          back_populates="member", cascade="all, delete-orphan")
    relationships_from = relationship("MemberRelationship", foreign_keys="MemberRelationship.member_id",  back_populates="member",  cascade="all, delete-orphan")
    relationships_to   = relationship("MemberRelationship", foreign_keys="MemberRelationship.related_id", back_populates="related", cascade="all, delete-orphan")
    user        = relationship("User", back_populates="member", uselist=False)


class MemberRelationship(Base):
    __tablename__ = "member_relationships"

    id          = Column(String, primary_key=True, default=gen_id)
    member_id   = Column(String, ForeignKey("members.id"), nullable=False)
    related_id  = Column(String, ForeignKey("members.id"), nullable=False)
    relation    = Column(String(50), nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    member  = relationship("Member", foreign_keys=[member_id],  back_populates="relationships_from")
    related = relationship("Member", foreign_keys=[related_id], back_populates="relationships_to")


class User(Base):
    __tablename__ = "users"

    id            = Column(String, primary_key=True, default=gen_id)
    member_id     = Column(String, ForeignKey("members.id"), nullable=True)
    email         = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role          = Column(String(20), default="member")
    reset_token   = Column(String(100), nullable=True)
    reset_expiry  = Column(DateTime, nullable=True)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    member = relationship("Member", back_populates="user")


class Room(Base):
    __tablename__ = "rooms"

    id         = Column(String, primary_key=True, default=gen_id)
    name       = Column(String(100), nullable=False)
    capacity   = Column(Integer, default=0)
    location   = Column(String(200))
    features   = Column(String(500))
    notes      = Column(Text)
    color      = Column(String(20), default="blue")
    created_at = Column(DateTime, default=datetime.utcnow)

    events = relationship("Event", back_populates="room")


class Event(Base):
    __tablename__ = "events"

    id              = Column(String, primary_key=True, default=gen_id)
    title           = Column(String(200), nullable=False)
    date            = Column(Date, nullable=False)
    start_time      = Column(String(10))
    end_time        = Column(String(10))
    type            = Column(String(50), default="Event")
    room_id         = Column(String, ForeignKey("rooms.id"), nullable=True)
    organizer       = Column(String(200))
    description     = Column(Text)
    volunteer_slots = Column(Integer, default=0)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    room = relationship("Room", back_populates="events")


class GivingRecord(Base):
    __tablename__ = "giving"

    id         = Column(String, primary_key=True, default=gen_id)
    member_id  = Column(String, ForeignKey("members.id"), nullable=True)
    date       = Column(Date, nullable=False)
    amount     = Column(Numeric(10, 2), nullable=False)
    type       = Column(String(50))
    fund       = Column(String(100), default="General Fund")
    notes      = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    member = relationship("Member", back_populates="giving")


class Pledge(Base):
    __tablename__ = "pledges"

    id             = Column(String, primary_key=True, default=gen_id)
    member_id      = Column(String, ForeignKey("members.id"), nullable=True)
    campaign       = Column(String(200))
    pledged_amount = Column(Numeric(10, 2), nullable=False)
    paid_amount    = Column(Numeric(10, 2), default=0)
    pledge_date    = Column(Date)
    end_date       = Column(Date)
    frequency      = Column(String(20), default="One-time")
    status         = Column(String(20), default="Active")
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    member = relationship("Member", back_populates="pledges")


class Ministry(Base):
    __tablename__ = "ministries"

    id          = Column(String, primary_key=True, default=gen_id)
    name        = Column(String(100), nullable=False)
    description = Column(Text)
    leader_id   = Column(String, ForeignKey("members.id"), nullable=True)
    color       = Column(String(20), default="blue")
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    leader      = relationship("Member", foreign_keys=[leader_id])
    memberships = relationship("MinistryMembership", back_populates="ministry", cascade="all, delete-orphan")


class MinistryMembership(Base):
    __tablename__ = "ministry_memberships"

    id          = Column(String, primary_key=True, default=gen_id)
    ministry_id = Column(String, ForeignKey("ministries.id"), nullable=False)
    member_id   = Column(String, ForeignKey("members.id"), nullable=False)
    role        = Column(String(50), default="Member")
    joined_date = Column(Date)
    created_at  = Column(DateTime, default=datetime.utcnow)

    ministry = relationship("Ministry", back_populates="memberships")
    member   = relationship("Member")


class OrgNode(Base):
    __tablename__ = "org_nodes"

    id         = Column(String, primary_key=True, default=gen_id)
    title      = Column(String(100), nullable=False)
    member_id  = Column(String, ForeignKey("members.id"), nullable=True)
    parent_id  = Column(String, ForeignKey("org_nodes.id"), nullable=True)
    sort_order = Column(Integer, default=0)
    notes      = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    member = relationship("Member", foreign_keys=[member_id])


class Group(Base):
    __tablename__ = "church_groups"

    id           = Column(String, primary_key=True, default=gen_id)
    name         = Column(String(100), nullable=False)
    group_type   = Column(String(50), default="Small Group")
    leader_id    = Column(String, ForeignKey("members.id"), nullable=True)
    meeting_day  = Column(String(20))
    meeting_time = Column(String(10))
    location     = Column(String(200))
    description  = Column(Text)
    is_active    = Column(Boolean, default=True)
    color        = Column(String(20), default="blue")
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    leader      = relationship("Member", foreign_keys=[leader_id])
    memberships = relationship("GroupMembership", back_populates="group", cascade="all, delete-orphan")


class GroupMembership(Base):
    __tablename__ = "group_memberships"

    id          = Column(String, primary_key=True, default=gen_id)
    group_id    = Column(String, ForeignKey("church_groups.id"), nullable=False)
    member_id   = Column(String, ForeignKey("members.id"), nullable=False)
    role        = Column(String(50), default="Member")
    joined_date = Column(Date)
    created_at  = Column(DateTime, default=datetime.utcnow)

    group  = relationship("Group", back_populates="memberships")
    member = relationship("Member")


class VolunteerShift(Base):
    __tablename__ = "volunteer_shifts"

    id             = Column(String, primary_key=True, default=gen_id)
    title          = Column(String(200), nullable=False)
    ministry       = Column(String(100))
    date           = Column(Date, nullable=False)
    start_time     = Column(String(10))
    end_time       = Column(String(10))
    room_id        = Column(String, ForeignKey("rooms.id"), nullable=True)
    location_notes = Column(String(200))
    description    = Column(Text)
    slots_needed   = Column(Integer, default=1)
    reminder_sent  = Column(Boolean, default=False)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    room    = relationship("Room")
    signups = relationship("ShiftSignup", back_populates="shift", cascade="all, delete-orphan")


class ShiftSignup(Base):
    __tablename__ = "shift_signups"

    id           = Column(String, primary_key=True, default=gen_id)
    shift_id     = Column(String, ForeignKey("volunteer_shifts.id"), nullable=False)
    member_id    = Column(String, ForeignKey("members.id"), nullable=False)
    signed_up_at = Column(DateTime, default=datetime.utcnow)

    shift  = relationship("VolunteerShift", back_populates="signups")
    member = relationship("Member")
