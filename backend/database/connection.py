"""
backend/database/connection.py

Database connection configuration for PostgreSQL using SQLAlchemy 2.x.

Responsibilities:
- Load DATABASE_URL from environment variables
- Create and configure SQLAlchemy Engine
- Enable connection pooling
- Validate configuration at startup

This module intentionally does NOT:
- Create database tables
- Create sessions
- Import models
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


# -----------------------------------------------------------------------------
# Environment Configuration
# -----------------------------------------------------------------------------
load_dotenv()


# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Database URL
# -----------------------------------------------------------------------------
DATABASE_URL: str | None = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable is not configured.")
    raise ValueError(
        "DATABASE_URL is missing. Please configure it in your .env file."
    )


# -----------------------------------------------------------------------------
# SQLAlchemy Engine
# -----------------------------------------------------------------------------
try:
    engine: Engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,      # Validates connections before use
        pool_size=10,            # Number of persistent connections
        max_overflow=20,         # Extra temporary connections
        pool_timeout=30,         # Seconds to wait for a connection
        pool_recycle=1800,       # Recycle stale connections (30 min)
        echo=False,              # Set True only for debugging
        future=True,             # SQLAlchemy 2.x behavior
    )

    logger.info("PostgreSQL engine initialized successfully.")

except SQLAlchemyError as exc:
    logger.exception(
        "Failed to initialize SQLAlchemy engine."
    )
    raise RuntimeError(
        "Database engine initialization failed."
    ) from exc