"""Migrations: attendance_records, member_checkins, settings, outline_json."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from backend.app.database import engine
from sqlalchemy import text

SQL = [
    'ALTER TABLE sermons ADD COLUMN IF NOT EXISTS outline_json TEXT',
    'CREATE TABLE IF NOT EXISTS settings ('
    '  key VARCHAR(120) PRIMARY KEY,'
    '  value TEXT,'
    '  is_secret BOOLEAN DEFAULT FALSE,'
    '  label VARCHAR(200),'
    '  "group" VARCHAR(50),'
    '  updated_at TIMESTAMP DEFAULT NOW()'
    ')',
    'CREATE TABLE IF NOT EXISTS attendance_records ('
    '  id VARCHAR(36) PRIMARY KEY,'
    '  date DATE NOT NULL,'
    '  service_type VARCHAR(50) DEFAULT \'Sunday Service\','
    '  headcount INTEGER DEFAULT 0,'
    '  notes TEXT,'
    '  created_at TIMESTAMP DEFAULT NOW(),'
    '  updated_at TIMESTAMP DEFAULT NOW()'
    ')',
    'CREATE TABLE IF NOT EXISTS member_checkins ('
    '  id VARCHAR(36) PRIMARY KEY,'
    '  record_id VARCHAR(36) REFERENCES attendance_records(id) ON DELETE SET NULL,'
    '  member_id VARCHAR(36) REFERENCES members(id) ON DELETE CASCADE,'
    '  date DATE NOT NULL,'
    '  checked_in_at TIMESTAMP DEFAULT NOW(),'
    '  method VARCHAR(20) DEFAULT \'kiosk\''
    ')',
]

with engine.connect() as conn:
    for sql in SQL:
        try:
            conn.execute(text(sql))
            conn.commit()
            print("OK:", sql[:70].strip())
        except Exception as e:
            print("SKIP:", e)

print("Migration complete.")
