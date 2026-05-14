"""One-time migration: add outline_json to sermons, create settings table."""
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
