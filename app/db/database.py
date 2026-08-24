"""
Database engine and session factory.

Uses SQLite via SQLAlchemy. The database file is created at ./app.db
relative to the working directory where the application is launched.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = "sqlite:///./app.db"

# check_same_thread=False is required for SQLite when used with FastAPI
# (requests can be handled by different threads).
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """Make SQLite safe for a background worker writing while the API reads.

    In SQLite's default ``delete`` journal mode a writer blocks every reader,
    so the automation worker updating job state would surface as
    ``database is locked`` on concurrent API requests. WAL lets readers run
    against the last committed snapshot while a write is in flight.

    ``synchronous=NORMAL`` matters on EBS specifically: each fsync is a network
    round-trip. Under WAL it stays durable against application crashes; only a
    host power-loss can lose the most recent transaction.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

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
