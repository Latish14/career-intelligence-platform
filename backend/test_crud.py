
"""
backend/test_crud.py

End-to-end CRUD test script for PostgreSQL.

Workflow:
1. Create database session
2. Create test user
3. Save test resume
4. Save test report
5. Retrieve user by ID
6. Retrieve resume by ID
7. Retrieve report by ID
8. Print results
9. Close session safely
"""

from __future__ import annotations

import logging
from typing import Any

from backend.database.session import SessionLocal
from backend.models.report import Report
from backend.models.resume import Resume
from backend.models.user import User

from backend.repositories.report_repository import ReportRepository
from backend.repositories.resume_repository import ResumeRepository
from backend.repositories.user_repository import UserRepository


# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# CRUD Test
# -----------------------------------------------------------------------------
def run_crud_test() -> None:
    """
    Execute complete CRUD workflow test.
    """

    db = SessionLocal()

    try:
        logger.info("Creating repositories...")

        user_repository = UserRepository(db)
        resume_repository = ResumeRepository(db)
        report_repository = ReportRepository(db)

        # ---------------------------------------------------------------------
        # Create User
        # ---------------------------------------------------------------------
        logger.info("Creating test user...")

        user = User(
            full_name="Test User",
            email="testuser@example.com",
            password_hash="hashed_password_123",
        )

        saved_user = user_repository.create_user(user)

        logger.info(
            "User created successfully. ID=%s",
            saved_user.id,
        )

        # ---------------------------------------------------------------------
        # Create Resume
        # ---------------------------------------------------------------------
        logger.info("Creating test resume...")

        resume = Resume(
            user_id=saved_user.id,
            filename="sample_resume.pdf",
            raw_text="""
            Python
            SQL
            FastAPI
            Machine Learning
            PostgreSQL
            """,
        )

        saved_resume = resume_repository.save_resume(
            resume
        )

        logger.info(
            "Resume created successfully. ID=%s",
            saved_resume.id,
        )

        # ---------------------------------------------------------------------
        # Create Report
        # ---------------------------------------------------------------------
        logger.info("Creating test report...")

        report_data: dict[str, Any] = {
            "skills_found": [
                "Python",
                "SQL",
                "FastAPI",
            ],
            "missing_skills": [
                "Docker",
                "AWS",
            ],
            "career_score": 82,
        }

        report = Report(
            user_id=saved_user.id,
            resume_id=saved_resume.id,
            report_json=report_data,
        )

        saved_report = report_repository.save_report(
            report
        )

        logger.info(
            "Report created successfully. ID=%s",
            saved_report.id,
        )

        # ---------------------------------------------------------------------
        # Read User
        # ---------------------------------------------------------------------
        retrieved_user = (
            user_repository.get_user_by_id(
                saved_user.id
            )
        )

        # ---------------------------------------------------------------------
        # Read Resume
        # ---------------------------------------------------------------------
        retrieved_resume = (
            resume_repository.get_resume_by_id(
                saved_resume.id
            )
        )

        # ---------------------------------------------------------------------
        # Read Report
        # ---------------------------------------------------------------------
        retrieved_report = (
            report_repository.get_report_by_id(
                saved_report.id
            )
        )

        # ---------------------------------------------------------------------
        # Output Results
        # ---------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("USER")
        print("=" * 60)
        print(retrieved_user)

        print("\n" + "=" * 60)
        print("RESUME")
        print("=" * 60)
        print(retrieved_resume)

        print("\n" + "=" * 60)
        print("REPORT")
        print("=" * 60)
        print(retrieved_report)

        if retrieved_report:
            print("\nREPORT JSON")
            print(retrieved_report.report_json)

        logger.info(
            "CRUD workflow completed successfully."
        )

    except Exception as exc:
        logger.exception(
            "CRUD test failed."
        )
        raise

    finally:
        logger.info(
            "Closing database session."
        )
        db.close()


# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    run_crud_test()
