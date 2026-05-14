"""
Seed script — populates FFC Church database with demo data.
Run once after first launch:  python seed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date, timedelta
from decimal import Decimal
from app.database import SessionLocal, engine, Base
from app import models

Base.metadata.create_all(bind=engine)
db = SessionLocal()

def run():
    if db.query(models.Member).count() > 0:
        print("Database already has data — skipping seed.")
        return

    today = date.today()
    y, m = today.year, today.month

    # ── Rooms ─────────────────────────────────────────────────────────────────
    rooms = [
        models.Room(id="r1", name="Sanctuary",       capacity=350, location="Main Building", features="Sound System, Projector, Livestream", color="blue"),
        models.Room(id="r2", name="Fellowship Hall", capacity=150, location="Main Building", features="Kitchen Access, Folding Tables, AV",   color="green"),
        models.Room(id="r3", name="Conference Room", capacity=20,  location="Admin Wing",    features="Whiteboard, TV Display, Video Conf.",  color="gold"),
        models.Room(id="r4", name="Youth Room",      capacity=60,  location="East Wing",     features="Sound System, Game Tables, Projector", color="red"),
        models.Room(id="r5", name="Chapel",          capacity=80,  location="Main Building", features="Quiet Space, Piano, Pew Seating",      color="blue"),
    ]
    db.add_all(rooms)

    # ── Members ───────────────────────────────────────────────────────────────
    members = [
        models.Member(id="m1",  first="James",    last="Anderson",  email="j.anderson@email.com",       phone="(555) 234-1001", status="Active",   since=date(2018, 3,12), ministry="Elder Board",       family_size=4),
        models.Member(id="m2",  first="Patricia", last="Williams",  email="p.williams@email.com",       phone="(555) 234-1002", status="Active",   since=date(2015, 9, 5), ministry="Women's Ministry",  family_size=3),
        models.Member(id="m3",  first="Robert",   last="Johnson",   email="r.johnson@email.com",        phone="(555) 234-1003", status="Active",   since=date(2020, 1,18), ministry="Worship Team",      family_size=2),
        models.Member(id="m4",  first="Susan",    last="Davis",     email="s.davis@email.com",          phone="(555) 234-1004", status="Active",   since=date(2019, 6,22), ministry="Usher",             family_size=5),
        models.Member(id="m5",  first="Michael",  last="Brown",     email="m.brown@email.com",          phone="(555) 234-1005", status="Active",   since=date(2021, 4,30), ministry="AV Team",           family_size=3),
        models.Member(id="m6",  first="Linda",    last="Martinez",  email="l.martinez@email.com",       phone="(555) 234-1006", status="Active",   since=date(2016,11,14), ministry="Sunday School",     family_size=4),
        models.Member(id="m7",  first="William",  last="Garcia",    email="w.garcia@email.com",         phone="(555) 234-1007", status="Visitor",  since=date(2026, 2, 9), ministry="",                  family_size=2),
        models.Member(id="m8",  first="Karen",    last="Thompson",  email="k.thompson@email.com",       phone="(555) 234-1008", status="Active",   since=date(2017, 7, 4), ministry="Prayer Team",       family_size=1),
        models.Member(id="m9",  first="David",    last="Wilson",    email="d.wilson@email.com",         phone="(555) 234-1009", status="Active",   since=date(2022, 8,15), ministry="Usher",             family_size=6),
        models.Member(id="m10", first="Jennifer", last="Lee",       email="j.lee@email.com",            phone="(555) 234-1010", status="Inactive", since=date(2014, 5,20), ministry="",                  family_size=2),
        models.Member(id="m11", first="Billy",    last="Simpson",   email="billyjacksimpson@gmail.com", phone="(555) 234-1011", status="Active",   since=date(2020, 1, 1), ministry="AV Team",           family_size=1),
    ]
    db.add_all(members)

    # ── Events ────────────────────────────────────────────────────────────────
    def d(day): return date(y, m, day)
    events = [
        models.Event(title="Sunday Morning Service",   date=d(18), start_time="09:00", end_time="11:00", type="Service",        room_id="r1", organizer="Pastor Ben",      volunteer_slots=8),
        models.Event(title="Sunday Evening Service",   date=d(18), start_time="18:00", end_time="19:30", type="Service",        room_id="r1", organizer="Pastor Ben",      volunteer_slots=4),
        models.Event(title="Youth Group",              date=d(20), start_time="18:30", end_time="20:00", type="Event",          room_id="r4", organizer="Youth Director",   volunteer_slots=3),
        models.Event(title="Elder Board Meeting",      date=d(21), start_time="19:00", end_time="20:30", type="Meeting",        room_id="r3", organizer="Ben (Rector)",     volunteer_slots=0),
        models.Event(title="Women's Bible Study",      date=d(22), start_time="10:00", end_time="11:30", type="Class",          room_id="r5", organizer="Women's Ministry", volunteer_slots=2),
        models.Event(title="AV Team Training",         date=d(22), start_time="18:00", end_time="19:00", type="Volunteer Slot", room_id="r2", organizer="Billy",            volunteer_slots=6),
        models.Event(title="Wednesday Prayer Service", date=d(22), start_time="07:00", end_time="08:00", type="Service",        room_id="r5", organizer="Pastor Ben",      volunteer_slots=0),
        models.Event(title="Men's Breakfast",          date=d(24), start_time="08:00", end_time="09:30", type="Event",          room_id="r2", organizer="Men's Ministry",  volunteer_slots=0),
        models.Event(title="Sunday Morning Service",   date=d(25), start_time="09:00", end_time="11:00", type="Service",        room_id="r1", organizer="Pastor Ben",      volunteer_slots=8),
    ]
    db.add_all(events)

    # ── Giving ────────────────────────────────────────────────────────────────
    giving = [
        models.GivingRecord(member_id="m1",  date=date(y,m, 4), amount=Decimal("250"), type="Tithe",         fund="General Fund"),
        models.GivingRecord(member_id="m2",  date=date(y,m, 4), amount=Decimal("150"), type="Tithe",         fund="General Fund"),
        models.GivingRecord(member_id="m3",  date=date(y,m, 4), amount=Decimal("100"), type="Tithe",         fund="General Fund"),
        models.GivingRecord(member_id="m4",  date=date(y,m, 4), amount=Decimal("200"), type="Offering",      fund="Building Fund"),
        models.GivingRecord(member_id="m5",  date=date(y,m, 4), amount=Decimal("75"),  type="Tithe",         fund="General Fund"),
        models.GivingRecord(member_id="m6",  date=date(y,m,11), amount=Decimal("300"), type="Tithe",         fund="General Fund"),
        models.GivingRecord(member_id="m8",  date=date(y,m,11), amount=Decimal("125"), type="Tithe",         fund="General Fund"),
        models.GivingRecord(member_id="m9",  date=date(y,m,11), amount=Decimal("180"), type="Tithe",         fund="General Fund"),
        models.GivingRecord(member_id="m11", date=date(y,m,11), amount=Decimal("50"),  type="Special Gift",  fund="AV Equipment",  notes="Monitor fund contribution"),
        models.GivingRecord(member_id="m1",  date=date(y,m, 4), amount=Decimal("500"), type="Building Fund", fund="Building Fund"),
        models.GivingRecord(member_id="m3",  date=date(y,m, 4), amount=Decimal("80"),  type="Missions",      fund="Missions"),
    ]
    db.add_all(giving)

    # ── Pledges ───────────────────────────────────────────────────────────────
    pledges = [
        models.Pledge(member_id="m1", campaign="Building Fund 2026", pledged_amount=Decimal("3000"), paid_amount=Decimal("1500"), pledge_date=date(y,1,1), end_date=date(y,12,31), frequency="Monthly"),
        models.Pledge(member_id="m2", campaign="Building Fund 2026", pledged_amount=Decimal("1200"), paid_amount=Decimal("600"),  pledge_date=date(y,1,1), end_date=date(y,12,31), frequency="Monthly"),
        models.Pledge(member_id="m4", campaign="Building Fund 2026", pledged_amount=Decimal("2400"), paid_amount=Decimal("1200"), pledge_date=date(y,1,1), end_date=date(y,12,31), frequency="Monthly"),
        models.Pledge(member_id="m6", campaign="Missions 2026",      pledged_amount=Decimal("600"),  paid_amount=Decimal("300"),  pledge_date=date(y,1,1), end_date=date(y,12,31), frequency="Monthly"),
        models.Pledge(member_id="m8", campaign="Building Fund 2026", pledged_amount=Decimal("500"),  paid_amount=Decimal("250"),  pledge_date=date(y,1,1), end_date=date(y, 6,30), frequency="Monthly"),
        models.Pledge(member_id="m9", campaign="Missions 2026",      pledged_amount=Decimal("1000"), paid_amount=Decimal("500"),  pledge_date=date(y,1,1), end_date=date(y,12,31), frequency="Monthly"),
    ]
    db.add_all(pledges)

    db.commit()
    print("✅  Seed data inserted successfully.")

if __name__ == "__main__":
    run()
    db.close()
