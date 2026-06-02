"""
api/routes/resume_routes.py
─────────────────────────────────────────────────────────────────────────────
FastAPI router for resume upload and career report generation.

Endpoint
--------
    POST /resume/upload
        Accepts a PDF or DOCX resume file, runs the full career intelligence
        pipeline, and returns a structured CareerReport.

Design
------
- APIRouter with prefix="/resume" and tag="Resume"
- Dependency injection for config and job_records (swappable in tests)
- Temporary file written to OS temp dir and always cleaned up
- All pipeline errors surfaced as appropriate HTTP status codes
- No database code — stateless per request
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Annotated
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from database.session import get_db
from models.resume import Resume
from models.report import Report

from repositories.resume_repository import ResumeRepository
from repositories.report_repository import ReportRepository

from services.career_report.report_generator import generate_career_report
from tinydb import TinyDB

from services.skill_engine.skill_extractor import (
    extract_skills,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ── Constants ─────────────────────────────────────────────────────────────────

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".docm"}
_MAX_FILE_SIZE_MB   = 10
_MAX_FILE_BYTES     = _MAX_FILE_SIZE_MB * 1024 * 1024


# ── Pydantic response models ──────────────────────────────────────────────────

class SkillItem(BaseModel):
    skill:      str
    confidence: float | None = None
    source:     str  | None = None


class MarketSkillItem(BaseModel):
    skill:      str
    demand_pct: float
    category:   str


class MissingSkillItem(BaseModel):
    skill:          str
    tier:           str
    demand_pct:     float
    priority_score: float
    explanation:    str


class PrioritySkillItem(BaseModel):
    rank:        int
    skill:       str
    final_score: float
    phase:       str
    tier:        str
    explanation: str


class RoadmapEntry(BaseModel):
    week:           int
    skill:          str
    priority:       str
    reason:         str
    duration_weeks: int


class CareerReportResponse(BaseModel):
    candidate_name:  str                    = Field(description="Name extracted from resume")
    target_role:     str                    = Field(description="Target job role")
    detected_skills: list[SkillItem]        = Field(description="Skills found in resume")
    market_skills:   list[MarketSkillItem]  = Field(description="Skills demanded by market")
    missing_skills:  list[MissingSkillItem] = Field(description="Skills not in resume but in market")
    priority_skills: list[PrioritySkillItem]= Field(description="Ranked learning priorities")
    roadmap:         list[RoadmapEntry]     = Field(description="Week-by-week learning plan")
    coverage_pct:    float                  = Field(description="Percentage of market skills the user has")
    placement_score: float                  = Field(description="Weighted placement readiness 0–100")


class ErrorResponse(BaseModel):
    detail: str
    stage:  str | None = None


# ── Dependencies ──────────────────────────────────────────────────────────────

class ReportConfig:
    """
    Injected configuration for the report generation pipeline.
    Override in tests or for different deployment environments.
    """
    def __init__(
        self,
        target_role:       str   = "Software Engineer",
        min_confidence:    float = 0.40,
        min_demand_pct:    float = 0.0,
        max_roadmap_steps: int   = 15,
    ) -> None:
        self.target_role       = target_role
        self.min_confidence    = min_confidence
        self.min_demand_pct    = min_demand_pct
        self.max_roadmap_steps = max_roadmap_steps


def get_report_config() -> ReportConfig:
    """Default dependency: reads from environment variables if set."""
    return ReportConfig(
        target_role    = os.getenv("DEFAULT_TARGET_ROLE", "Software Engineer"),
        min_confidence = float(os.getenv("MIN_SKILL_CONFIDENCE", "0.40")),
        min_demand_pct = float(os.getenv("MIN_DEMAND_PCT",        "0.0")),
    )


def get_job_records() -> list[dict]:
    """
    Load jobs from jobs.json and convert them into
    the format expected by report_generator.
    """

    jobs_path = (
        Path(__file__).resolve().parents[3]
        / "job_engine"
        / "jobs.json"
    )

    print("JOBS PATH:", jobs_path)

    db = TinyDB(str(jobs_path))

    # Read from the TinyDB table named "jobs"
    jobs_table = db.table("jobs")

    all_jobs = jobs_table.all()

    print("TOTAL JOBS IN JSON:", len(all_jobs))

    job_records = []

    for job in all_jobs:

        description = job.get(
            "description",
            "",
        )

        result = extract_skills(
            description,
        )

        skills = [
            skill["skill"]
            for skill in result["skills"]
        ]

        if skills:
            job_records.append(
                {
                    "job_id": job.get(
                        "job_id",
                        "",
                    ),
                    "skills": skills,
                }
            )

    print(
        "TOTAL JOB RECORDS:",
        len(job_records),
    )

    if job_records:
        print(
            "FIRST RECORD:",
            job_records[0],
        )

    return job_records


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_upload(file: UploadFile) -> None:
    """
    Validate file extension and content type.

    Raises
    ------
    HTTPException 400 : unsupported file type
    HTTPException 400 : missing filename
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file has no filename.",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            ),
        )

    # Content-type guard (browsers may send application/octet-stream)
    allowed_ct = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/octet-stream",   # generic fallback
    }
    if file.content_type and file.content_type not in allowed_ct:
        logger.warning(
            "Unexpected content-type %r for file %r — proceeding with extension check.",
            file.content_type, file.filename,
        )


async def _save_temp(file: UploadFile) -> str:
    """
    Stream UploadFile to a named temporary file.

    Returns the absolute path of the temp file.

    Raises
    ------
    HTTPException 413 : file exceeds _MAX_FILE_BYTES
    HTTPException 500 : IO error while writing
    """
    suffix = Path(file.filename).suffix.lower()
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="resume_")

    try:
        total = 0
        with os.fdopen(tmp_fd, "wb") as fh:
            while chunk := await file.read(65_536):   # 64 KB chunks
                total += len(chunk)
                if total > _MAX_FILE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"File exceeds maximum allowed size of "
                            f"{_MAX_FILE_SIZE_MB} MB."
                        ),
                    )
                fh.write(chunk)

        logger.info("Saved upload to temp file: %s (%d bytes)", tmp_path, total)
        return tmp_path

    except HTTPException:
        _cleanup(tmp_path)
        raise
    except OSError as exc:
        _cleanup(tmp_path)
        logger.error("Failed to write temp file: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file. Please try again.",
        ) from exc


def _cleanup(path: str) -> None:
    """Silently remove a temp file if it exists."""
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:                          # noqa: BLE001
        logger.warning("Could not clean up temp file: %s", path)


def _build_response(raw: dict) -> CareerReportResponse:
    """
    Convert a raw CareerReport dict into the Pydantic response model.
    Fields missing from raw dicts are defaulted to empty lists / zero.
    """
    return CareerReportResponse(
        candidate_name  = raw.get("candidate_name", ""),
        target_role     = raw.get("target_role",    ""),
        detected_skills = [SkillItem(**s) for s in raw.get("detected_skills", [])],
        market_skills   = [MarketSkillItem(**_coerce_market(s))
                           for s in raw.get("market_skills", [])],
        missing_skills  = [MissingSkillItem(**_coerce_missing(s))
                           for s in raw.get("missing_skills", [])],
        priority_skills = [PrioritySkillItem(**_coerce_priority(s))
                           for s in raw.get("priority_skills", [])],
        roadmap         = [RoadmapEntry(**_coerce_roadmap(e))
                           for e in raw.get("roadmap", [])],
        coverage_pct    = float(raw.get("coverage_pct",    0.0)),
        placement_score = float(raw.get("placement_score", 0.0)),
    )


# Light field coercers — tolerate missing or extra keys from pipeline dicts

def _coerce_market(d: dict) -> dict:
    return {"skill": d.get("skill",""), "demand_pct": float(d.get("demand_pct",0)),
            "category": d.get("category","other")}

def _coerce_missing(d: dict) -> dict:
    return {"skill": d.get("skill",""), "tier": d.get("tier",""),
            "demand_pct": float(d.get("demand_pct",0)),
            "priority_score": float(d.get("priority_score",0)),
            "explanation": d.get("explanation","")}

def _coerce_priority(d: dict) -> dict:
    return {"rank": int(d.get("rank",0)), "skill": d.get("skill",""),
            "final_score": float(d.get("final_score",0)),
            "phase": d.get("phase",""), "tier": d.get("tier",""),
            "explanation": d.get("explanation","")}

def _coerce_roadmap(d: dict) -> dict:
    return {"week": int(d.get("week",1)), "skill": d.get("skill",""),
            "priority": d.get("priority",""), "reason": d.get("reason",""),
            "duration_weeks": int(d.get("duration_weeks",1))}


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/resume", tags=["Resume"])


@router.post(
    "/upload",
    response_model   = CareerReportResponse,
    status_code      = status.HTTP_200_OK,
    summary          = "Upload a resume and receive a career intelligence report",
    responses        = {
        400: {"model": ErrorResponse, "description": "Invalid file"},
        413: {"model": ErrorResponse, "description": "File too large"},
        415: {"model": ErrorResponse, "description": "Unsupported file type"},
        422: {"model": ErrorResponse, "description": "Pipeline validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def upload_resume(
    file: Annotated[UploadFile, File(...)],
    config: Annotated[ReportConfig, Depends(get_report_config)],
    job_records: Annotated[list[dict], Depends(get_job_records)],
    db: Session = Depends(get_db),
) -> CareerReportResponse:
    """
    Upload a resume (PDF or DOCX) and receive a full career intelligence report.

    The report includes:
    - **detected_skills**  — skills extracted from the resume
    - **market_skills**    — skills demanded by the job market
    - **missing_skills**   — gaps between resume and market (prioritised)
    - **priority_skills**  — ranked learning priorities with explanations
    - **roadmap**          — week-by-week learning plan
    - **coverage_pct**     — percentage of market skills the candidate has
    - **placement_score**  — weighted readiness score (0–100)
    """
    logger.info(
        "POST /resume/upload  filename=%r  content_type=%r",
        file.filename, file.content_type,
    )

    # ── Step 1: validate ──────────────────────────────────────────────────────
    _validate_upload(file)

    # ── Step 2: save to temp file ─────────────────────────────────────────────
    tmp_path = await _save_temp(file)

    try:
        # ── Step 3: run pipeline ──────────────────────────────────────────────
        logger.info("Running career report pipeline for %r", file.filename)

        report = generate_career_report(
            resume_path       = tmp_path,
            job_records       = job_records,
            target_role       = config.target_role,
            min_confidence    = config.min_confidence,
            min_demand_pct    = config.min_demand_pct,
            max_roadmap_steps = config.max_roadmap_steps,
        )

        if not report["success"]:
            error_msg = report.get("error") or "Pipeline failed without error message."
            logger.error("Pipeline failed for %r: %s", file.filename, error_msg)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error_msg,
            )
        
        # ------------------------------------------------------------------
        # Save Resume
        # ------------------------------------------------------------------

        resume_repo = ResumeRepository(db)

        resume_record = Resume(
            user_id=1,
            filename=file.filename,
            raw_text="TEMP_TEXT",
        )

        saved_resume = resume_repo.save_resume(
            resume_record
        )

        # ------------------------------------------------------------------
        # Save Report
        # ------------------------------------------------------------------

        report_repo = ReportRepository(db)

        report_record = Report(
            user_id=1,
            resume_id=saved_resume.id,
            report_json=report,
        )

        report_repo.save_report(
            report_record
        )
        
        

        # ── Step 4: serialise and return ──────────────────────────────────────
        response = _build_response(report)
        logger.info(
            "Report complete  candidate=%r  coverage=%.1f%%  "
            "missing=%d  roadmap=%d",
            response.candidate_name, response.coverage_pct,
            len(response.missing_skills), len(response.roadmap),
        )
        return response

    except HTTPException:
        raise   # re-raise FastAPI exceptions unchanged

    except Exception as exc:               # noqa: BLE001
        logger.exception("Unexpected error processing %r: %s", file.filename, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again.",
        ) from exc

    finally:
        _cleanup(tmp_path)
        logger.debug("Temp file cleaned up: %s", tmp_path)