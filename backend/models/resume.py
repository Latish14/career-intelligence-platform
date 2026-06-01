"""
backend/models/resume.py

SQLAlchemy model for storing uploaded resumes.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class Resume(Base):
    """
    Uploaded resume associated with a user.
    """

    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    user = relationship(
        "User",
        back_populates="resumes",
    )

    reports = relationship(
        "Report",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
    reports = relationship(
        "Report",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
    user = relationship(
        "User",
        back_populates="resumes",
    )

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"Resume("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"filename='{self.filename}'"
            f")"
        )
