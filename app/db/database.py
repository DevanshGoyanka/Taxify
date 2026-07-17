"""
Database engine and session factory.

Uses SQLite via SQLAlchemy. The database file is created at ./app.db
relative to the working directory where the application is launched.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = "sqlite:///./app.db"

# check_same_thread=False is required for SQLite when used with FastAPI
# (requests can be handled by different threads).
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Each call to SessionLocal() produces a new database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class that all ORM models inherit from."""
    pass


def get_db():
    """
    Yield a database session and ensure it is closed after use.

    Intended to be used as a FastAPI dependency via Depends(get_db).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
