"""
Database connection and session management.
Uses SQLAlchemy with psycopg2 (synchronous) to match the existing server stack.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://fcc_user:fcc_password@localhost:5432/fcc_church"
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency: yields a database session, closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
