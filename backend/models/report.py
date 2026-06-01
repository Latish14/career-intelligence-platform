
"""
backend/models/report.py

SQLAlchemy model for storing generated Career Intelligence Reports.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class Report(Base):
    """
    Generated career intelligence report.

    Stores structured report output in PostgreSQL JSONB format.
    """

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    report_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    user = relationship(
        "User",
        back_populates="reports",
    )

    resume = relationship(
        "Resume",
        back_populates="reports",
    )

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"Report("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"resume_id={self.resume_id}"
            f")"
        )
