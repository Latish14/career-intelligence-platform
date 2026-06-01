"""
backend/database/base.py

Shared SQLAlchemy Declarative Base for all ORM models.

All database models should inherit from this Base class to ensure
consistent metadata management and ORM behavior across the application.

This module intentionally contains only the declarative base definition.
Engine configuration, session management, and model declarations should
be implemented in their respective modules.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    Example:
        from database.base import Base

        class User(Base):
            __tablename__ = "users"
            ...

    SQLAlchemy automatically collects model metadata through this base,
    enabling schema creation, migrations, and ORM operations.
    """

    pass