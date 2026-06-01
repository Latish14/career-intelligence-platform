"""
backend/database/session.py

Database session management for the application.

Responsibilities:
- Create a reusable SQLAlchemy Session factory
- Provide FastAPI dependency injection for database sessions
- Ensure proper session cleanup after each request

This module should be used by API routes and services that need
database access.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from database.connection import engine


# -----------------------------------------------------------------------------
# Session Factory
# -----------------------------------------------------------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# -----------------------------------------------------------------------------
# Database Dependency
# -----------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Yields:
        Session: Active SQLAlchemy database session.

    Ensures:
        - Session is closed after request completion
        - Connections are returned to the pool
    """
    db: Session = SessionLocal()

    try:
        yield db
    finally:
        db.close()