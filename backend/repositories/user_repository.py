
"""
backend/repositories/user_repository.py

Repository layer for User database operations.

Responsibilities:
- Create users
- Retrieve users by ID
- Retrieve users by email
- List users
- Handle database exceptions
- Provide structured logging

Notes:
- Uses SQLAlchemy 2.x ORM style
- Does not contain business logic
- Does not contain API logic
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models.user import User


# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# User Repository
# -----------------------------------------------------------------------------
class UserRepository:
    """
    Repository class for User database operations.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy database session.
        """
        self.db = db

    # -------------------------------------------------------------------------
    # Create User
    # -------------------------------------------------------------------------
    def create_user(self, user: User) -> User:
        """
        Create a new user.

        Args:
            user: User model instance.

        Returns:
            Created User object.

        Raises:
            RuntimeError: If database operation fails.
        """
        try:
            logger.info(
                "Creating user with email: %s",
                user.email,
            )

            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

            logger.info(
                "User created successfully. ID=%s",
                user.id,
            )

            return user

        except SQLAlchemyError as exc:
            self.db.rollback()

            logger.exception(
                "Failed to create user."
            )

            raise RuntimeError(
                "Failed to create user."
            ) from exc

    # -------------------------------------------------------------------------
    # Get User By ID
    # -------------------------------------------------------------------------
    def get_user_by_id(
        self,
        user_id: int,
    ) -> Optional[User]:
        """
        Retrieve a user by ID.

        Args:
            user_id: User primary key.

        Returns:
            User object if found, otherwise None.
        """
        try:
            logger.debug(
                "Fetching user by ID=%s",
                user_id,
            )

            statement = select(User).where(
                User.id == user_id
            )

            return self.db.scalar(statement)

        except SQLAlchemyError as exc:
            logger.exception(
                "Failed to retrieve user by ID."
            )

            raise RuntimeError(
                "Failed to retrieve user."
            ) from exc

    # -------------------------------------------------------------------------
    # Get User By Email
    # -------------------------------------------------------------------------
    def get_user_by_email(
        self,
        email: str,
    ) -> Optional[User]:
        """
        Retrieve a user by email.

        Args:
            email: User email address.

        Returns:
            User object if found, otherwise None.
        """
        try:
            logger.debug(
                "Fetching user by email=%s",
                email,
            )

            statement = select(User).where(
                User.email == email
            )

            return self.db.scalar(statement)

        except SQLAlchemyError as exc:
            logger.exception(
                "Failed to retrieve user by email."
            )

            raise RuntimeError(
                "Failed to retrieve user."
            ) from exc

    # -------------------------------------------------------------------------
    # List Users
    # -------------------------------------------------------------------------
    def list_users(self) -> List[User]:
        """
        Retrieve all users.

        Returns:
            List of User objects.
        """
        try:
            logger.debug(
                "Fetching all users."
            )

            statement = select(User)

            result = self.db.scalars(statement)

            return list(result.all())

        except SQLAlchemyError as exc:
            logger.exception(
                "Failed to list users."
            )

            raise RuntimeError(
                "Failed to retrieve users."
            ) from exc
