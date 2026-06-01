"""
backend/repositories/report_repository.py

Repository layer for Career Report database operations.

Responsibilities:
- Save generated reports
- Retrieve report by ID
- Retrieve reports belonging to a user
- Delete reports
- Handle database exceptions
- Provide structured logging

Notes:
- Uses SQLAlchemy 2.x ORM style
- Supports PostgreSQL JSON/JSONB fields
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

from models.report import Report


logger = logging.getLogger(__name__)


class ReportRepository:
    """
    Repository class for Career Report database operations.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize repository.

        Args:
            db: SQLAlchemy database session.
        """
        self.db = db

    def save_report(
        self,
        report: Report,
    ) -> Report:
        """
        Save a generated career report.

        Supports PostgreSQL JSON/JSONB fields stored
        within the Report model.

        Args:
            report: Report model instance.

        Returns:
            Persisted Report object.

        Raises:
            RuntimeError: If database operation fails.
        """
        try:
            logger.info(
                "Saving report for user_id=%s",
                getattr(report, "user_id", None),
            )

            self.db.add(report)
            self.db.commit()
            self.db.refresh(report)

            logger.info(
                "Report saved successfully. report_id=%s",
                report.id,
            )

            return report

        except SQLAlchemyError as exc:
            self.db.rollback()

            logger.exception(
                "Failed to save report."
            )

            raise RuntimeError(
                "Failed to save report."
            ) from exc

    def get_report_by_id(
        self,
        report_id: int,
    ) -> Optional[Report]:
        """
        Retrieve a report by ID.

        Args:
            report_id: Report primary key.

        Returns:
            Report object if found, otherwise None.
        """
        try:
            logger.debug(
                "Fetching report by ID=%s",
                report_id,
            )

            statement = select(Report).where(
                Report.id == report_id
            )

            return self.db.scalar(statement)

        except SQLAlchemyError as exc:
            logger.exception(
                "Failed to retrieve report."
            )

            raise RuntimeError(
                "Failed to retrieve report."
            ) from exc

    def get_reports_by_user(
        self,
        user_id: int,
    ) -> List[Report]:
        """
        Retrieve all reports belonging to a user.

        Args:
            user_id: User primary key.

        Returns:
            List of Report objects.
        """
        try:
            logger.debug(
                "Fetching reports for user_id=%s",
                user_id,
            )

            statement = select(Report).where(
                Report.user_id == user_id
            )

            result = self.db.scalars(statement)

            return list(result.all())

        except SQLAlchemyError as exc:
            logger.exception(
                "Failed to retrieve user reports."
            )

            raise RuntimeError(
                "Failed to retrieve user reports."
            ) from exc

    def delete_report(
        self,
        report_id: int,
    ) -> bool:
        """
        Delete a report by ID.

        Args:
            report_id: Report primary key.

        Returns:
            True if deleted, False otherwise.

        Raises:
            RuntimeError: If database operation fails.
        """
        try:
            logger.info(
                "Deleting report ID=%s",
                report_id,
            )

            statement = delete(Report).where(
                Report.id == report_id
            )

            result = self.db.execute(statement)

            self.db.commit()

            deleted = result.rowcount > 0

            if deleted:
                logger.info(
                    "Report deleted successfully. ID=%s",
                    report_id,
                )
            else:
                logger.warning(
                    "Report not found. ID=%s",
                    report_id,
                )

            return deleted

        except SQLAlchemyError as exc:
            self.db.rollback()

            logger.exception(
                "Failed to delete report."
            )

            raise RuntimeError(
                "Failed to delete report."
            ) from exc
