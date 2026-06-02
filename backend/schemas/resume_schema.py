"""
backend/schemas/resume_schema.py
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResumeResponse(BaseModel):
    """
    Response schema for a stored resume.
    """

    id: int
    user_id: int
    filename: str
    raw_text: str
    uploaded_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class ResumeListResponse(BaseModel):
    """
    Response schema for multiple resumes.
    """

    count: int
    resumes: list[ResumeResponse]

    model_config = ConfigDict(
        from_attributes=True
    )