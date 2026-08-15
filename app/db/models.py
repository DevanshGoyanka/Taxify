"""
SQLAlchemy ORM models.

Tables:
  - User           : registered users with hashed passwords.
  - SavedReturn    : a user's submitted ITR calculation, with both
                     the raw input and the computed result stored as JSON text.
  - Client         : a client managed by a user.
  - ClientITR      : ITR form data and calculation status for a client+AY.
  - AutomationJob  : an automated download job (Playwright → ITD portal).
"""

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class User(Base):
    """
    Represents a registered user.

    Passwords are never stored in plaintext — only the bcrypt hash.
    """

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class SavedReturn(Base):
    """
    Stores one saved ITR calculation for a user.

    itr_type       : either "ITR1" or "ITR4" — indicates which form was filed.
    input_data     : JSON-serialised dict of the user's form inputs.
    computed_result: JSON-serialised dict of the tax engine output.
    """

    __tablename__ = "saved_return"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    itr_type: Mapped[str] = mapped_column(String(10), nullable=False)          # "ITR1" | "ITR4"
    input_data: Mapped[str] = mapped_column(Text, nullable=False)               # JSON text
    computed_result: Mapped[str] = mapped_column(Text, nullable=False)          # JSON text
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Client(Base):
    """
    Represents a client managed by a user.
    """

    __tablename__ = "client"
    __table_args__ = (
        UniqueConstraint("user_id", "pan", name="uq_client_user_pan"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    public_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pan: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(25), nullable=False, default="", server_default="")
    middle_name: Mapped[str] = mapped_column(String(25), nullable=False, default="", server_default="")
    surname: Mapped[str] = mapped_column(String(75), nullable=False, default="", server_default="")
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    mobile: Mapped[str] = mapped_column(String(20), nullable=True)
    aadhaar: Mapped[str] = mapped_column(String(20), nullable=True)
    dob: Mapped[str] = mapped_column(String(10), nullable=True)
    portal_password: Mapped[str] = mapped_column(Text, nullable=True)
    archived_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ClientITR(Base):
    """
    Stores ITR form data and calculation status for a client and assessment year.
    """

    __tablename__ = "client_itr"
    __table_args__ = (
        UniqueConstraint("client_id", "year", name="uq_client_itr_client_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("client.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[str] = mapped_column(String(10), nullable=False)
    itr_type: Mapped[str] = mapped_column(String(10), nullable=False, default="ITR-1")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Not Started")
    form_data: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    computed_result: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AutomationJob(Base):
    """
    An automated download job via Playwright into the ITD portal.

    Tracks the full lifecycle: queued → running → completed / failed.
    Stores download file paths on completion.
    """

    __tablename__ = "automation_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("client.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="DOWNLOAD_ALL"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )
    assessment_year: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )
    fiscal_year: Mapped[str] = mapped_column(String(10), nullable=False)

    # ---- Progress tracking (JSON-serialised) ----
    steps_completed: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )
    current_step: Mapped[str] = mapped_column(String(100), nullable=True)
    status_message: Mapped[str] = mapped_column(String(500), nullable=True)
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ---- Results ----
    files_downloaded: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}"
    )
    artifact_outcomes: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}"
    )
    parsed_results: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}"
    )
    ais_ref_id: Mapped[str] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str] = mapped_column(String(1000), nullable=True)

    # ---- Timestamps ----
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Retry ----
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
