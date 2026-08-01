"""
Database initialisation helper.

Call create_tables() once at application startup to create all tables
that do not yet exist.  This is intentionally simple — no Alembic, no
migrations, no destructive operations.
"""

# Import models so that SQLAlchemy's metadata is populated before
# create_all() is called.  The imports must come before Base is used.
import uuid

import app.db.models  # noqa: F401  — side-effect import registers the models

from sqlalchemy import inspect, text

from app.db.database import Base, engine


def _apply_additive_sqlite_migrations() -> None:
    """Add lifecycle columns required by existing SQLite installations.

    This is a temporary additive migration bridge until Alembic is introduced.
    It never drops or rewrites existing tables or return data.
    """
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    if "client" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("client")}
    with engine.begin() as connection:
        if "public_id" not in columns:
            connection.execute(text("ALTER TABLE client ADD COLUMN public_id VARCHAR(36)"))
        if "archived_at" not in columns:
            connection.execute(text("ALTER TABLE client ADD COLUMN archived_at DATETIME"))

        missing_ids = connection.execute(
            text("SELECT id FROM client WHERE public_id IS NULL OR public_id = ''")
        ).fetchall()
        for (client_id,) in missing_ids:
            connection.execute(
                text("UPDATE client SET public_id = :public_id WHERE id = :client_id"),
                {"public_id": str(uuid.uuid4()), "client_id": client_id},
            )

        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_client_public_id "
                "ON client (public_id)"
            )
        )
        duplicate_pan_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM ("
                "SELECT user_id, pan FROM client GROUP BY user_id, pan HAVING COUNT(*) > 1"
                ")"
            )
        ).scalar_one()
        if duplicate_pan_count == 0:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_client_user_pan "
                    "ON client (user_id, pan)"
                )
            )
        else:
            print(
                "[WARN] Client PAN uniqueness index deferred: "
                f"{duplicate_pan_count} duplicate user/PAN group(s) require reconciliation."
            )

        duplicate_year_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM ("
                "SELECT client_id, year FROM client_itr "
                "GROUP BY client_id, year HAVING COUNT(*) > 1"
                ")"
            )
        ).scalar_one()
        if duplicate_year_count == 0:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_client_itr_client_year "
                    "ON client_itr (client_id, year)"
                )
            )
        else:
            print(
                "[WARN] Client/year uniqueness index deferred: "
                f"{duplicate_year_count} duplicate client/year group(s) require reconciliation."
            )


def create_tables() -> None:
    """
    Create all tables defined in the ORM metadata if they do not exist.

    Safe to call repeatedly — SQLAlchemy uses CREATE TABLE IF NOT EXISTS
    semantics internally via checkfirst=True (the default).
    """
    Base.metadata.create_all(bind=engine)
    _apply_additive_sqlite_migrations()
    print("[OK] Database tables created and additive migrations applied.")


if __name__ == "__main__":
    create_tables()
