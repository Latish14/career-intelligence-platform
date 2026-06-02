
"""
backend/api/routes/resume_management_routes.py

FastAPI routes for managing stored resumes.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.session import get_db
from repositories.resume_repository import ResumeRepository
from schemas.resume_schema import (
    ResumeResponse,
    ResumeListResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/resumes",
    tags=["Resumes"],
)


@router.get(
    "/{user_id}",
    response_model=ResumeListResponse,
    status_code=status.HTTP_200_OK,
)
def get_user_resumes(
    user_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Retrieve all resumes belonging to a user.

    Args:
        user_id: User identifier.
        db: Database session.

    Returns:
        JSON response containing resumes.
    """
    try:
        logger.info(
            "Fetching resumes for user_id=%s",
            user_id,
        )

        repository = ResumeRepository(db)

        resumes = repository.get_user_resumes(
            user_id=user_id,
        )

        return ResumeListResponse(
            count=len(resumes),
            resumes=resumes,
        )

    except Exception as exc:
        logger.exception(
            "Failed to retrieve resumes for user_id=%s",
            user_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resumes.",
        ) from exc


@router.get(
    "/resume/{resume_id}",
    response_model=ResumeResponse,
    status_code=status.HTTP_200_OK,
)
def get_resume_by_id(
    resume_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Retrieve a resume by ID.

    Args:
        resume_id: Resume identifier.
        db: Database session.

    Returns:
        JSON response containing resume.
    """
    try:
        logger.info(
            "Fetching resume ID=%s",
            resume_id,
        )

        repository = ResumeRepository(db)

        resume = repository.get_resume_by_id(
            resume_id=resume_id,
        )

        if resume is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found.",
            )

        return resume

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Failed to retrieve resume ID=%s",
            resume_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resume.",
        ) from exc


@router.delete(
    "/{resume_id}",
    status_code=status.HTTP_200_OK,
)
def delete_resume(
    resume_id: int,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Delete a resume.

    Args:
        resume_id: Resume identifier.
        db: Database session.

    Returns:
        Success message.
    """
    try:
        logger.info(
            "Deleting resume ID=%s",
            resume_id,
        )

        repository = ResumeRepository(db)

        deleted = repository.delete_resume(
            resume_id=resume_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found.",
            )

        return {
            "message": (
                f"Resume {resume_id} deleted successfully."
            )
        }

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Failed to delete resume ID=%s",
            resume_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete resume.",
        ) from exc
