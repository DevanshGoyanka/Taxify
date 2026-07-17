"""
SQLAlchemy ORM models.

Defines exactly two tables:
  - User           : registered users with hashed passwords.
  - SavedReturn    : a user's submitted ITR-1 or ITR-4 calculation, with both
                     the raw input and the computed result stored as JSON text.
"""

import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pan: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    mobile: Mapped[str] = mapped_column(String(20), nullable=True)
    aadhaar: Mapped[str] = mapped_column(String(20), nullable=True)
    dob: Mapped[str] = mapped_column(String(10), nullable=True)
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

