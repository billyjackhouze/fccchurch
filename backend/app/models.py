"""
SQLAlchemy ORM models for FFC Church Management System.
"""
import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, backref
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
    status      = Column(String(20), default="Active")   # Active | Visitor | Inactive
    since       = Column(Date)
    ministry    = Column(String(200))
    family_size = Column(Integer, default=1)
    pronouns    = Column(String(50))                      # e.g. He/Him, She/Her, They/Them
    notes       = Column(Text)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    giving      = relationship("GivingRecord",    back_populates="member",           cascade="all, delete-orphan")
    pledges     = relationship("Pledge",          back_populates="member",           cascade="all, delete-orphan")
    # Family relationships this member has with others (as the "from" side)
    relationships_from = relationship("MemberRelationship", foreign_keys="MemberRelationship.member_id",  back_populates="member",  cascade="all, delete-orphan")
    # Family relationships where this member is the related person (as the "to" side)
    relationships_to   = relationship("MemberRelationship", foreign_keys="MemberRelationship.related_id", back_populates="related", cascade="all, delete-orphan")


class MemberRelationship(Base):
    """Links two members together with a relationship type (Partner, Child, Parent, etc.)"""
    __tablename__ = "member_relationships"

    id          = Column(String, primary_key=True, default=gen_id)
    member_id   = Column(String, ForeignKey("members.id"), nullable=False)   # e.g. John
    related_id  = Column(String, ForeignKey("members.id"), nullable=False)   # e.g. Jane
    relation    = Column(String(50), nullable=False)                          # Partner | Child | Parent | Sibling | Guardian | Other
    created_at  = Column(DateTime, default=datetime.utcnow)

    member  = relationship("Member", foreign_keys=[member_id],  back_populates="relationships_from")
    related = relationship("Member", foreign_keys=[related_id], back_populates="relationships_to")


class Room(Base):
    __tablename__ = "rooms"

    id       = Column(String, primary_key=True, default=gen_id)
    name     = Column(String(100), nullable=False)
    capacity = Column(Integer, default=0)
    location = Column(String(200))
    features = Column(String(500))
    notes    = Column(Text)
    color    = Column(String(20), default="blue")  # blue | green | gold | red (UI accent)
    created_at = Column(DateTime, default=datetime.utcnow)

    events   = relationship("Event", back_populates="room")


class Event(Base):
    __tablename__ = "events"

    id              = Column(String, primary_key=True, default=gen_id)
    title           = Column(String(200), nullable=False)
    date            = Column(Date, nullable=False)
    start_time      = Column(String(10))   # HH:MM (24h)
    end_time        = Column(String(10))   # HH:MM (24h)
    type            = Column(String(50), default="Event")  # Service | Meeting | Volunteer Slot | Event | Class | Other
    room_id         = Column(String, ForeignKey("rooms.id"), nullable=True)
    organizer       = Column(String(200))
    description     = Column(Text)
    volunteer_slots = Column(Integer, default=0)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    room = relationship("Room", back_populates="events")


class GivingRecord(Base):
    __tablename__ = "giving"

    id        = Column(String, primary_key=True, default=gen_id)
    member_id = Column(String, ForeignKey("members.id"), nullable=True)
    date      = Column(Date, nullable=False)
    amount    = Column(Numeric(10, 2), nullable=False)
    type      = Column(String(50))  # Tithe | Offering | Building Fund | Missions | Special Gift
    fund      = Column(String(100), default="General Fund")
    notes     = Column(String(500))
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
    frequency      = Column(String(20), default="One-time")  # One-time | Weekly | Monthly | Annual
    status         = Column(String(20), default="Active")    # Active | Fulfilled | Lapsed
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    member = relationship("Member", back_populates="pledges")
