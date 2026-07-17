"""
Database initialisation helper.

Call create_tables() once at application startup to create all tables
that do not yet exist.  This is intentionally simple — no Alembic, no
migrations, no destructive operations.
"""

# Import models so that SQLAlchemy's metadata is populated before
# create_all() is called.  The imports must come before Base is used.
import app.db.models  # noqa: F401  — side-effect import registers the models

from app.db.database import Base, engine


def create_tables() -> None:
    """
    Create all tables defined in the ORM metadata if they do not exist.

    Safe to call repeatedly — SQLAlchemy uses CREATE TABLE IF NOT EXISTS
    semantics internally via checkfirst=True (the default).
    """
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created (or already exist).")


if __name__ == "__main__":
    create_tables()
