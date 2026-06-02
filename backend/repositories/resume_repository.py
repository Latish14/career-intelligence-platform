"""
backend/repositories/resume_repository.py

Repository layer for Resume database operations.

Responsibilities:
- Save resume records
- Retrieve resume by ID
- Retrieve resumes belonging to a user
- Delete resumes
- Handle database exceptions
- Provide structured logging

Notes:
- Uses SQLAlchemy 2.x ORM style
- Contains only data access logic
- Does not contain business logic
- Does not contain API logic
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models.resume import Resume


logger = logging.getLogger(__name__)


class ResumeRepository:
    """
    Repository class for Resume database operations.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize repository.

        Args:
            db: SQLAlchemy database session.
        """
        self.db = db

    def save_resume(self, resume: Resume) -> Resume:
        """
        Save a resume record.

        Args:
            resume: Resume model instance.

        Returns:
            Persisted Resume object.

        Raises:
            RuntimeError: If database operation fails.
        """
        try:
            logger.info(
                "Saving resume for user_id=%s",
                getattr(resume, "user_id", None),
            )

            self.db.add(resume)
            self.db.commit()
            self.db.refresh(resume)

            logger.info(
                "Resume saved successfully. resume_id=%s",
                resume.id,
            )

            return resume

        except SQLAlchemyError as exc:
            self.db.rollback()

            logger.exception(
                "Failed to save resume."
            )

            raise RuntimeError(
                "Failed to save resume."
            ) from exc

    def get_resume_by_id(
        self,
        resume_id: int,
    ) -> Optional[Resume]:
        """
        Retrieve a resume by ID.

        Args:
            resume_id: Resume primary key.

        Returns:
            Resume object if found, otherwise None.
        """
        try:
            logger.debug(
                "Fetching resume by ID=%s",
                resume_id,
            )

            statement = select(Resume).where(
                Resume.id == resume_id
            )

            return self.db.scalar(statement)

        except SQLAlchemyError as exc:
            logger.exception(
                "Failed to retrieve resume."
            )

            raise RuntimeError(
                "Failed to retrieve resume."
            ) from exc

    def get_user_resumes(
        self,
        user_id: int,
    ) -> List[Resume]:
        """
        Retrieve all resumes belonging to a user.

        Args:
            user_id: User primary key.

        Returns:
            List of Resume objects.
        """
        try:
            logger.debug(
                "Fetching resumes for user_id=%s",
                user_id,
            )

            statement = select(Resume).where(
                Resume.user_id == user_id
            )

            result = self.db.scalars(statement)

            return list(result.all())

        except SQLAlchemyError as exc:
            logger.exception(
                "Failed to retrieve user resumes."
            )

            raise RuntimeError(
                "Failed to retrieve user resumes."
            ) from exc

    def delete_resume(
        self,
        resume_id: int,
    ) -> bool:
        """
        Delete a resume by ID.

        Args:
            resume_id: Resume primary key.

        Returns:
            True if deleted, False if not found.

        Raises:
            RuntimeError: If database operation fails.
        """
        try:
            logger.info(
                "Deleting resume ID=%s",
                resume_id,
            )

            statement = delete(Resume).where(
                Resume.id == resume_id
            )

            result = self.db.execute(statement)

            self.db.commit()

            deleted = result.rowcount > 0

            if deleted:
                logger.info(
                    "Resume deleted successfully. ID=%s",
                    resume_id,
                )
            else:
                logger.warning(
                    "Resume not found. ID=%s",
                    resume_id,
                )

            return deleted

        except SQLAlchemyError as exc:
            self.db.rollback()

            logger.exception(
                "Failed to delete resume."
            )

            raise RuntimeError(
                "Failed to delete resume."
            ) from exc