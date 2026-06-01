"""
backend/api/routes/report_routes.py

FastAPI routes for managing stored career reports.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.session import get_db
from repositories.report_repository import ReportRepository


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


@router.get(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
)
def get_reports_by_user(
    user_id: int,
    db: Session = Depends(get_db),
) -> List[dict]:
    """
    Retrieve all reports belonging to a user.

    Args:
        user_id: User identifier.
        db: Database session.

    Returns:
        List of reports.
    """
    try:
        logger.info(
            "Fetching reports for user_id=%s",
            user_id,
        )

        repository = ReportRepository(db)

        reports = repository.get_reports_by_user(
            user_id=user_id,
        )

        return [report.report_json for report in reports]

    except Exception as exc:
        logger.exception(
            "Failed to fetch reports for user_id=%s",
            user_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve reports.",
        ) from exc


@router.get(
    "/report/{report_id}",
    status_code=status.HTTP_200_OK,
)
def get_report_by_id(
    report_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Retrieve a report by ID.

    Args:
        report_id: Report identifier.
        db: Database session.

    Returns:
        CareerReportResponse
    """
    try:
        logger.info(
            "Fetching report ID=%s",
            report_id,
        )

        repository = ReportRepository(db)

        report = repository.get_report_by_id(
            report_id=report_id,
        )

        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found.",
            )

        return report.report_json

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Failed to fetch report ID=%s",
            report_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve report.",
        ) from exc


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_200_OK,
)
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Delete a report.

    Args:
        report_id: Report identifier.
        db: Database session.

    Returns:
        Success message.
    """
    try:
        logger.info(
            "Deleting report ID=%s",
            report_id,
        )

        repository = ReportRepository(db)

        deleted = repository.delete_report(
            report_id=report_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found.",
            )

        return {
            "message": (
                f"Report {report_id} deleted successfully."
            )
        }

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Failed to delete report ID=%s",
            report_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete report.",
        ) from exc
