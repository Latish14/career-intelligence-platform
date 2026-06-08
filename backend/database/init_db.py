"""
backend/backend.database/init_db.py

Database initialization utilities.

Responsibilities:
- Create all backend.database tables defined by SQLAlchemy models
- Log initialization status
- Handle backend.database initialization errors

Note:
- All model modules must be imported before calling
  initialize_database() so that SQLAlchemy can register
  their metadata with Base.
"""

from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError

from models import user, resume, skill, job

from database.base import Base
from database.connection import engine


# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Database Initialization
# -----------------------------------------------------------------------------
def initialize_database() -> None:
    """
    Create all tables registered with SQLAlchemy Base metadata.

    Raises:
        RuntimeError: If table creation fails.
    """
    try:
        logger.info("Starting backend.database initialization...")

        Base.metadata.create_all(bind=engine)

        logger.info("Database tables created successfully.")

    except SQLAlchemyError as exc:
        logger.exception("Database initialization failed.")

        raise RuntimeError(
            "Failed to initialize backend.database tables."
        ) from exc
        
        
if __name__ == "__main__":
    initialize_database()